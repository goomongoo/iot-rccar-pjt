/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

typedef struct {
	// [Input] Sensors
	int16_t ax, ay, az;		// MPU6050 Accel
	int16_t gx, gy, gz;		// MPU6050 Gyro
	uint32_t distance_cm;	// Ultrasonic Distance

	// [Output] Actuators
	int16_t throttle;		// -100 ~ 100
	int16_t steer;			// -100 ~ 100
} RcCarState_t;

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */
extern volatile uint32_t g_distance;
/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */
void MPU6050_Init(I2C_HandleTypeDef *hi2c);
void MPU6050_Read_Accel(I2C_HandleTypeDef *hi2c, int16_t *ax, int16_t *ay, int16_t *az);
void MPU6050_Read_Gyro(I2C_HandleTypeDef *hi2c, int16_t *gx, int16_t *gy, int16_t *gz);
/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define US_TRIG_Pin GPIO_PIN_6
#define US_TRIG_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */
#define MOUNT_TYPE	1	// 1 or 2

#define OFFSET_AX_TYPE_1	-250
#define OFFSET_AY_TYPE_1	-2400
#define OFFSET_AZ_TYPE_1	-6000
#define OFFSET_GX_TYPE_1	-200
#define OFFSET_GY_TYPE_1	-840
#define OFFSET_GZ_TYPE_1	40

#define OFFSET_AX_TYPE_2	0
#define OFFSET_AY_TYPE_2	0
#define OFFSET_AZ_TYPE_2	0
#define OFFSET_GX_TYPE_2	0
#define OFFSET_GY_TYPE_2	0
#define OFFSET_GZ_TYPE_2	0
/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
