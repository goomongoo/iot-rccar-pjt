/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
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

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "usart.h"
#include "i2c.h"
#include "motorhat.h"

extern volatile uint32_t g_distance;
extern uint8_t rx_buffer[];
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */
RcCarState_t g_carState = {0};
/* USER CODE END Variables */
/* Definitions for defaultTask */
osThreadId_t defaultTaskHandle;
const osThreadAttr_t defaultTask_attributes = {
  .name = "defaultTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityLow,
};
/* Definitions for ControlTask */
osThreadId_t ControlTaskHandle;
const osThreadAttr_t ControlTask_attributes = {
  .name = "ControlTask",
  .stack_size = 512 * 4,
  .priority = (osPriority_t) osPriorityRealtime,
};
/* Definitions for TelemetryTask */
osThreadId_t TelemetryTaskHandle;
const osThreadAttr_t TelemetryTask_attributes = {
  .name = "TelemetryTask",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for CommRxTask */
osThreadId_t CommRxTaskHandle;
const osThreadAttr_t CommRxTask_attributes = {
  .name = "CommRxTask",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityHigh,
};
/* Definitions for cmdQueue */
osMessageQueueId_t cmdQueueHandle;
const osMessageQueueAttr_t cmdQueue_attributes = {
  .name = "cmdQueue"
};
/* Definitions for stateMutex */
osMutexId_t stateMutexHandle;
const osMutexAttr_t stateMutex_attributes = {
  .name = "stateMutex"
};

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */
void Remap_Axis(int16_t rx, int16_t ry, int16_t rz, int16_t *ox, int16_t *oy, int16_t *oz)
{
#if (MOUNT_TYPE == 1)
	*ox = -ry;
	*oy = rx;
	*oz = rz;

#elif (MOUNT_TYPE == 2)
	*ox = rx;
	*oy = rz;
	*oz = -ry;

#endif
}
/* USER CODE END FunctionPrototypes */

void StartDefaultTask(void *argument);
void StartControlTask(void *argument);
void StartTelemetryTask(void *argument);
void StartCommRxTask(void *argument);

void MX_FREERTOS_Init(void); /* (MISRA C 2004 rule 8.1) */

/**
  * @brief  FreeRTOS initialization
  * @param  None
  * @retval None
  */
void MX_FREERTOS_Init(void) {
  /* USER CODE BEGIN Init */

  /* USER CODE END Init */
  /* Create the mutex(es) */
  /* creation of stateMutex */
  stateMutexHandle = osMutexNew(&stateMutex_attributes);

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* Create the queue(s) */
  /* creation of cmdQueue */
  cmdQueueHandle = osMessageQueueNew (10, sizeof(uint16_t), &cmdQueue_attributes);

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of defaultTask */
  defaultTaskHandle = osThreadNew(StartDefaultTask, NULL, &defaultTask_attributes);

  /* creation of ControlTask */
  ControlTaskHandle = osThreadNew(StartControlTask, NULL, &ControlTask_attributes);

  /* creation of TelemetryTask */
  TelemetryTaskHandle = osThreadNew(StartTelemetryTask, NULL, &TelemetryTask_attributes);

  /* creation of CommRxTask */
  CommRxTaskHandle = osThreadNew(StartCommRxTask, NULL, &CommRxTask_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  /* add threads, ... */
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

}

/* USER CODE BEGIN Header_StartDefaultTask */
/**
  * @brief  Function implementing the defaultTask thread.
  * @param  argument: Not used
  * @retval None
  */
/* USER CODE END Header_StartDefaultTask */
void StartDefaultTask(void *argument)
{
  /* USER CODE BEGIN StartDefaultTask */
  /* Infinite loop */
  for(;;)
  {
    osDelay(1000);
  }
  /* USER CODE END StartDefaultTask */
}

/* USER CODE BEGIN Header_StartControlTask */
/**
* @brief Function implementing the ControlTask thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartControlTask */
void StartControlTask(void *argument)
{
  /* USER CODE BEGIN StartControlTask */
	int16_t raw_ax, raw_ay, raw_az;
	int16_t raw_gx, raw_gy, raw_gz;
	int16_t body_ax, body_ay, body_az;
	int16_t body_gx, body_gy, body_gz;

	int16_t target_thr = 0;
	int16_t target_str = 0;

	MotorHat_Init();
	Motor_SetSteer(0);
	Motor_SetThrottle(0);

  /* Infinite loop */
  for(;;)
  {
	  // 1. Read Sensor Data
	  // MPU6050
	  MPU6050_Read_Accel(&hi2c1, &raw_ax, &raw_ay, &raw_az);
	  MPU6050_Read_Gyro(&hi2c1, &raw_gx, &raw_gy, &raw_gz);

	  Remap_Axis(raw_ax, raw_ay, raw_az, &body_ax, &body_ay, &body_az);
	  Remap_Axis(raw_gx, raw_gy, raw_gz, &body_gx, &body_gy, &body_gz);

#if (MOUNT_TYPE == 1)
	  body_ax -= OFFSET_AX_TYPE_1;
	  body_ay -= OFFSET_AY_TYPE_1;
	  body_az -= OFFSET_AZ_TYPE_1;
	  body_gx -= OFFSET_GX_TYPE_1;
	  body_gy -= OFFSET_GY_TYPE_1;
	  body_gz -= OFFSET_GZ_TYPE_1;
#elif (MOUNT_TYPE == 2)
	  body_ax -= OFFSET_AX_TYPE_2;
	  body_ay -= OFFSET_AY_TYPE_2;
	  body_az -= OFFSET_AZ_TYPE_2;
	  body_gx -= OFFSET_GX_TYPE_2;
	  body_gy -= OFFSET_GY_TYPE_2;
	  body_gz -= OFFSET_GZ_TYPE_2;
#endif

	  // Ultrasonic
	  HAL_GPIO_WritePin(US_TRIG_GPIO_Port, US_TRIG_Pin, GPIO_PIN_SET);
	  // Very short delay
	  for (int i = 0; i < 72 * 10; i++) __NOP();
	  HAL_GPIO_WritePin(US_TRIG_GPIO_Port, US_TRIG_Pin, GPIO_PIN_RESET);

	  // Update data
	  if (osMutexAcquire(stateMutexHandle, 10) == osOK)
	  {
		  g_carState.ax = body_ax;
		  g_carState.ay = body_ay;
		  g_carState.az = body_az;
		  g_carState.gx = body_gx;
		  g_carState.gy = body_gy;
		  g_carState.gz = body_gz;
		  g_carState.distance_cm = g_distance;
		  target_thr = g_carState.throttle;
		  target_str = g_carState.steer;

		  osMutexRelease(stateMutexHandle);
	  }

	  // Failsafe
	  if (g_distance > 0 && g_distance < 10 && target_thr > 0)
	  {
		  target_thr = 0;
	  }

	  // Run motor
	  Motor_SetThrottle(target_thr);
	  Motor_SetSteer(target_str);

	  // Every 20ms
	  osDelay(20);
  }
  /* USER CODE END StartControlTask */
}

/* USER CODE BEGIN Header_StartTelemetryTask */
/**
* @brief Function implementing the TelemetryTask thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTelemetryTask */
void StartTelemetryTask(void *argument)
{
  /* USER CODE BEGIN StartTelemetryTask */
	char tx_buffer[128];
	RcCarState_t current_state;

  /* Infinite loop */
  for(;;)
  {
	  // Copy data
	  if (osMutexAcquire(stateMutexHandle, 10) == osOK)
	  {
		  current_state = g_carState;
		  osMutexRelease(stateMutexHandle);
	  }

	  // Packet formatting ($TEL)
	  // spec: $TEL, AX, AY, AZ, GX, GY, GZ, DIST, THROTTLE, STEER
	  int len = sprintf(tx_buffer, "$TEL,%d,%d,%d,%d,%d,%d,%lu,%d,%d\r\n",
			  current_state.ax, current_state.ay, current_state.az,
			  current_state.gx, current_state.gy, current_state.gz,
			  current_state.distance_cm,
			  current_state.throttle, current_state.steer);

	  // Transmit UART DMA
	  //if (HAL_UART_GetState(&huart1) == HAL_UART_STATE_READY)
	  //{
		  //HAL_UART_Transmit_DMA(&huart1, (uint8_t *)tx_buffer, len);
	  //}

	  // Every 50ms
	  osDelay(50);
  }
  /* USER CODE END StartTelemetryTask */
}

/* USER CODE BEGIN Header_StartCommRxTask */
/**
* @brief Function implementing the CommRxTask thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartCommRxTask */
void StartCommRxTask(void *argument)
{
  /* USER CODE BEGIN StartCommRxTask */
	char *token;
	char cmd_copy[64];

  /* Infinite loop */
  for(;;)
  {
	  // 1. Wait for data (blocking)
	  osThreadFlagsWait(0x01, osFlagsWaitAny, osWaitForever);

	  // 2. Copy data
	  strcpy(cmd_copy, (char *)rx_buffer);

	  // 3. parsing logic
	  token = strtok(cmd_copy, ",");

	  if (token != NULL)
	  {
		  if (!strcmp(token, "$CMD"))
		  {
			  // Format: $CMD,THROTTLE,STEER
			  char *s_thr = strtok(NULL, ",");
			  char *s_str = strtok(NULL, ",");

			  if (s_thr != NULL && s_str != NULL)
			  {
				  int16_t val_thr = atoi(s_thr);
				  int16_t val_str = atoi(s_str);

				  if (osMutexAcquire(stateMutexHandle, 10) == osOK)
				  {
					  g_carState.throttle = val_thr;
					  g_carState.steer = val_str;
					  osMutexRelease(stateMutexHandle);
				  }
			  }
		  }
		  else if (!strcmp(token, "$TUN"))
		  {
			  // Format: $TUN,TYPE,VALUE
			  //TODO
		  }
	  }
	  memset(rx_buffer, 0, 64);
  }
  /* USER CODE END StartCommRxTask */
}

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */

/* USER CODE END Application */

