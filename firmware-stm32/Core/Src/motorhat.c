/*
 * motorhat.c
 *
 *  Created on: Dec 3, 2025
 *      Author: mongoo
 */

#include "motorhat.h"
#include <math.h>
#include <stdlib.h>

extern I2C_HandleTypeDef hi2c2;

// I2C Address (0x6F << 1 -> 0xDE)
#define MOTORHAT_ADDR       (0x6F << 1)

// Registers
#define __MODE1             0x00
#define __MODE2             0x01
#define __PRESCALE          0xFE
#define __LED0_ON_L         0x06
#define __ALL_LED_ON_L      0xFA
#define __ALL_LED_OFF_L     0xFC

// Bits
#define __RESTART           0x80
#define __SLEEP             0x10
#define __ALLCALL           0x01
#define __OUTDRV            0x04

// DC Motor (Throttle) - Channel 13, 12, 11
#define PIN_PWM             13
#define PIN_IN1             12
#define PIN_IN2             11

// Servo Motor (Steering) - Channel 0
#define PIN_SERVO           0

// Servo Calibration Values (User Test Data)
// Left: 580, Mid: 430, Right: 280
#define SERVO_VAL_LEFT      580
#define SERVO_VAL_RIGHT     280
#define SERVO_VAL_MID       430

// ==========================================
// [Internal Functions]
// ==========================================

static void write8(uint8_t reg, uint8_t value)
{
	uint8_t data[2] = { reg, value };
	HAL_I2C_Master_Transmit(&hi2c2, MOTORHAT_ADDR, data, 2, 10);
}

static uint8_t readU8(uint8_t reg)
{
	uint8_t value = 0;
	HAL_I2C_Master_Transmit(&hi2c2, MOTORHAT_ADDR, &reg, 1, 10);
	HAL_I2C_Master_Transmit(&hi2c2, MOTORHAT_ADDR, &value, 1, 10);
	return value;
}

static void setPWM(int channel, int on, int off)
{
	write8(__LED0_ON_L + 4 * channel, on & 0xFF);
	write8(__LED0_ON_L + 4 * channel + 1, on >> 8);
	write8(__LED0_ON_L + 4 * channel + 2, off & 0xFF);
	write8(__LED0_ON_L + 4 * channel + 3, off >> 8);
}

static void setAllPWM(int on, int off)
{
	write8(__ALL_LED_ON_L, on & 0xFF);
	write8(__ALL_LED_ON_L + 1, on >> 8);
	write8(__ALL_LED_OFF_L, off & 0xFF);
	write8(__ALL_LED_OFF_L + 1, off >> 8);
}

static void setPWMFreq(int freq)
{
	float prescaleval = 25000000.0;
	prescaleval /= 4096.0;
	prescaleval /= (float)freq;
	prescaleval -= 1.0;

	int prescale = (int)(prescaleval + 0.5);

	uint8_t oldmode = readU8(__MODE1);
	uint8_t newmode = (oldmode & 0x7F) | 0x10;	// sleep

	write8(__MODE1, newmode);
	write8(__PRESCALE, (uint8_t)prescale);
	write8(__MODE1, oldmode);

	HAL_Delay(5);
	write8(__MODE1, oldmode | 0x80);	// restart
}

// ==========================================
// [Public Functions]
// ==========================================

void MotorHat_Init(void)
{
	setAllPWM(0, 0);
	write8(__MODE2, __OUTDRV);
	write8(__MODE1, __ALLCALL);
	HAL_Delay(5);

	uint8_t mode1 = readU8(__MODE1);
	mode1 = mode1 & ~__SLEEP;	// wake up
	write8(__MODE1, mode1);
	HAL_Delay(5);

	// 60Hz
	setPWMFreq(60);
}

void Motor_SetSteer(int16_t angle)
{
	// Input Constraints
	if (angle < -100) angle = -100;
	if (angle > 100) angle = 100;

	// Mapping: -100(Left/580) ~ +100(Right/280)
	// Formula: y = 430 + (angle * -1.5)
	// -100 * -1.5 = +150 -> 430 + 150 = 580 (OK)
	// +100 * -1.5 = -150 -> 430 - 150 = 280 (OK)

	int pwm_val = 430 - (int)(angle * 0.9f);

	setPWM(PIN_SERVO, 0, pwm_val);
}

void Motor_SetThrottle(int16_t speed)
{
	// Input Constraints
	if (speed < -100) speed = -100;
	if (speed > 100) speed = 100;

	// Map 0~100 to 0~4095 PWM
	int pwm_val = abs(speed) * 4095 / 100;

	if (speed > 0)
	{
		// Forward: IN1(High), IN2(Low)
		setPWM(PIN_IN1, 0, 4096); // Full OFF
		setPWM(PIN_IN2, 4096, 0); // Full ON
		setPWM(PIN_PWM, 0, pwm_val);
    }
    else if (speed < 0)
    {
    	// Backward: IN1(Low), IN2(High)
    	setPWM(PIN_IN1, 4096, 0); // Full ON
    	setPWM(PIN_IN2, 0, 4096); // Full OFF
    	setPWM(PIN_PWM, 0, pwm_val);
    }
    else
    {
    	// Stop
    	setPWM(PIN_IN1, 0, 4096);
    	setPWM(PIN_IN2, 0, 4096);
    	setPWM(PIN_PWM, 0, 4096); // PWM 0
    }
}
