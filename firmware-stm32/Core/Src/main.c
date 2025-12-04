/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
#include "main.h"
#include "cmsis_os.h"
#include "dma.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define MPU6050_ADDR	(0x68 << 1)
#define RX_BUFFER_SIZE	64
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
uint32_t ic_val1 = 0;
uint32_t ic_val2 = 0;
uint32_t difference = 0;
uint8_t is_first_captured;
volatile uint32_t g_distance = 0;

uint8_t rx_buffer[RX_BUFFER_SIZE];
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
void MX_FREERTOS_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
extern osThreadId_t CommRxTaskHandle;
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART1_UART_Init();
  MX_I2C1_Init();
  MX_I2C2_Init();
  MX_TIM4_Init();
  /* USER CODE BEGIN 2 */

  // 1. Start Ultrasonic Timer (TIM4 Channel 2)
  HAL_TIM_IC_Start_IT(&htim4, TIM_CHANNEL_2);

  // 2. Init MPU6050
  MPU6050_Init(&hi2c1);

  // 3. UART Rx Init
  HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buffer, RX_BUFFER_SIZE);

  /* USER CODE END 2 */

  /* Init scheduler */
  osKernelInitialize();  /* Call init function for freertos objects (in cmsis_os2.c) */
  MX_FREERTOS_Init();

  /* Start scheduler */
  osKernelStart();

  /* We should never get here as control is now taken by the scheduler */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
	if (htim->Instance == TIM4) // PB7 (Echo)
	{
		if (is_first_captured == 0) // Rising Edge
		{
			ic_val1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
			is_first_captured = 1;
			// Change polarity to falling edge and wait for next interrupt
			__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_FALLING);
		}
		else // Falling edge
		{
			ic_val2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);

			// Deal with timer overflow
			if (ic_val2 > ic_val1)
			{
				difference = ic_val2 - ic_val1;
			}
			else
			{
				difference = (0xFFFF - ic_val1) + ic_val2;
			}

			// Calculate distance (us / 58 = cm)
			g_distance = difference / 58;

			is_first_captured = 0;
			// Roll back polarity to rising edge
			__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_RISING);
		}
	}
}

void MPU6050_Init(I2C_HandleTypeDef *hi2c)
{
	uint8_t check;
	uint8_t data;

	// Check WHO_AM_I
	HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x75, 1, &check, 1, 1000);

	if (check == (MPU6050_ADDR >> 1))
	{
		// PWR_MGMT_1 (0x6B) -> 0 (Wake up)
		data = 0;
		HAL_I2C_Mem_Write(hi2c, MPU6050_ADDR, 0x6B, 1, &data, 1, 1000);
	}
}

void MPU6050_Read_Accel(I2C_HandleTypeDef *hi2c, int16_t *ax, int16_t *ay, int16_t *az)
{
	uint8_t rec_data[6];

	// Read 6 bytes from ACCEL_XOUT_H (0x3B)
	HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x3B, 1, rec_data, 6, 1000);

	*ax = (int16_t)(rec_data[0] << 8 | rec_data[1]);
	*ay = (int16_t)(rec_data[2] << 8 | rec_data[3]);
	*az = (int16_t)(rec_data[4] << 8 | rec_data[5]);
}

void MPU6050_Read_Gyro(I2C_HandleTypeDef *hi2c, int16_t *gx, int16_t *gy, int16_t *gz)
{
	uint8_t rec_data[6];

	// Read 6 bytes from GYRO_XOUT_H (0x43)
	HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x43, 1, rec_data, 6, 1000);

	*gx = (int16_t)(rec_data[0] << 8 | rec_data[1]);
	*gy = (int16_t)(rec_data[2] << 8 | rec_data[3]);
	*gz = (int16_t)(rec_data[4] << 8 | rec_data[5]);
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
	if (huart->Instance == USART1)
	{
		if (Size < RX_BUFFER_SIZE)
		{
			rx_buffer[Size] = '\0';
		}

		// Send signal to CommRxTask
		if (CommRxTaskHandle != NULL)
		{
			osThreadFlagsSet(CommRxTaskHandle, 0x01);
		}

		HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buffer, RX_BUFFER_SIZE);
	}
}
/* USER CODE END 4 */

/**
  * @brief  Period elapsed callback in non blocking mode
  * @note   This function is called  when TIM1 interrupt took place, inside
  * HAL_TIM_IRQHandler(). It makes a direct call to HAL_IncTick() to increment
  * a global variable "uwTick" used as application time base.
  * @param  htim : TIM handle
  * @retval None
  */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  /* USER CODE BEGIN Callback 0 */

  /* USER CODE END Callback 0 */
  if (htim->Instance == TIM1)
  {
    HAL_IncTick();
  }
  /* USER CODE BEGIN Callback 1 */

  /* USER CODE END Callback 1 */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
