# STM32 RC Car Firmware

L1 Control Layer Technical Report

본 문서는 “AI 예지 정비(Predictive Maintenance) 및 사람 추종 자율주행 RC Car” 프로젝트에서 L1 제어 계층(STM32 Nucleo-F103RB)이 수행하는 기능, 구조, 통신 규격, FreeRTOS 기반 스케줄링, MotorHat(PCA9685) 제어 방식, 센서 입력 처리(Accel/Gyro/초음파), 안전 제어 로직 등을 상세하게 기술한다. 또한 프로젝트 명세서에서 요구한 기능들이 실제 코드에서 어떻게 구현되었는지를 정리한다.

---

## 1. 시스템 개요

### 1.1 L1 제어 계층의 역할

명세서 기반 전체 아키텍처에서 L1(STM32)은 다음 실시간 제어 기능들을 수행한다.

1. 센서 입력의 고속 수집

   - MPU6050 가속도/자이로 수집
   - 초음파 거리 센서 측정(TIM4 Input Capture)

2. 모터 및 서보 제어

   - MotorHat(PCA9685) 기반 PWM 제어
   - DC 모터 속도 제어(Throttle)
   - 서보 조향 제어(Steering)

3. 실시간 Fail-Safe

   - 장애물 거리 10cm 이하 시 강제 정지

4. 텔레메트리 데이터 전송

   - `$TEL` 패킷을 약 50 ms 주기로 UART DMA 전송

5. 주행 명령 수신

   - `$CMD` 패킷 파싱 후 throttle/steer 상태값 반영

6. FreeRTOS 기반 태스크 스케줄링
   - ControlTask (20 ms 주기)
   - TelemetryTask (50 ms 주기)
   - CommRxTask (UART Idle 이벤트 기반)
   - DefaultTask (Background)

명세서가 요구한 하드 실시간 제어 기능이 모두 반영된 구조이다.

---

## 2. 코드 구조

프로젝트의 핵심 펌웨어 파일 구조는 다음과 같다.

```text
/Core
 ├── Inc
 │    ├── main.h
 │    ├── motorhat.h
 │    └── ...
 ├── Src
 │    ├── main.c
 │    ├── freertos.c
 │    ├── motorhat.c
 │    └── ...
```

각 파일의 역할은 다음과 같다.

- `main.c`  
  시스템 초기화, 클럭 설정, 주변장치 초기화(I2C, UART, TIM, DMA), FreeRTOS 커널 시작, 인터럽트 콜백 구현

- `main.h`  
  전역 타입 정의, 외부 변수 선언, 핀/오프셋 상수 정의, MPU6050 관련 함수 프로토타입 선언

- `freertos.c`  
  FreeRTOS 오브젝트(Task, Mutex, Queue) 생성 및 각 Task 구현(ControlTask, TelemetryTask, CommRxTask 등)

- `motorhat.c` / `motorhat.h`  
  MotorHat(PCA9685) 제어용 추상화 레이어. 서보 조향, DC 모터 스로틀 제어, PWM 설정 관련 함수 구현

---

## 3. 주요 데이터 구조 및 전역 변수

### 3.1 RcCarState_t

RC Car의 센서/제어 상태를 한 번에 표현하기 위한 구조체이다. FreeRTOS Mutex로 보호되면서 다수 Task 간 공유된다.

```c
typedef struct {
    // [Input] Sensors
    int16_t ax, ay, az;     // MPU6050 Accel
    int16_t gx, gy, gz;     // MPU6050 Gyro
    uint32_t distance_cm;   // Ultrasonic Distance

    // [Output] Actuators
    int16_t throttle;       // -100 ~ 100
    int16_t steer;          // -100 ~ 100
} RcCarState_t;
```

해당 구조체 인스턴스 `g_carState`는 `freertos.c`에서 정의한다.

```c
RcCarState_t g_carState = {0};
```

이 상태값은 다음과 같이 사용한다.

- ControlTask에서 센서 값을 업데이트하고 현재 목표 throttle/steer 값을 읽는다.
- TelemetryTask에서 텔레메트리 송신 시 참조용으로 복사한다.
- CommRxTask에서 `$CMD` 명령을 수신했을 때 throttle/steer 값을 갱신한다.

### 3.2 거리 측정 관련 변수

`main.c`에서는 초음파 센서 거리 계산을 위해 다음 변수를 사용한다.

```c
uint32_t ic_val1 = 0;
uint32_t ic_val2 = 0;
uint32_t difference = 0;
uint8_t is_first_captured;
volatile uint32_t g_distance = 0;
```

- `ic_val1`, `ic_val2`는 각각 상승엣지, 하강엣지에서 캡처된 타이머 카운트 값이다.
- `difference`는 두 값의 차이(펄스 폭, us 단위에 대응)를 의미한다.
- `g_distance`는 실제 계산된 거리(cm) 값이다.

### 3.3 UART 수신 버퍼

UART DMA 수신을 위한 링 버퍼가 다음과 같이 정의된다.

```c
#define RX_BUFFER_SIZE 64
uint8_t rx_buffer[RX_BUFFER_SIZE];
```

Idle Line 인터럽트 발생 시 `HAL_UARTEx_RxEventCallback`에서 이 버퍼의 내용을 문자열로 가공하고, CommRxTask에 처리 요청을 보낸다.

---

## 4. 센서 입력 처리

### 4.1 MPU6050 가속도/자이로 (I2C1)

#### 4.1.1 초기화

`MPU6050_Init(I2C_HandleTypeDef *hi2c)` 함수에서 다음 절차를 수행한다.

1. WHO_AM_I 레지스터(0x75)를 읽어 센서가 정상 응답하는지 확인한다.
2. PWR_MGMT_1(0x6B) 레지스터에 0을 기록하여 Sleep 모드에서 깨어나도록 한다.

```c
void MPU6050_Init(I2C_HandleTypeDef *hi2c)
{
    uint8_t check;
    uint8_t data;

    HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x75, 1, &check, 1, 1000);

    if (check == (MPU6050_ADDR >> 1))
    {
        data = 0;
        HAL_I2C_Mem_Write(hi2c, MPU6050_ADDR, 0x6B, 1, &data, 1, 1000);
    }
}
```

#### 4.1.2 가속도/자이로 데이터 읽기

- 가속도는 0x3B(ACCEL_XOUT_H)부터 6바이트를 읽어 X, Y, Z를 16비트 signed로 조합한다.
- 자이로는 0x43(GYRO_XOUT_H)부터 6바이트를 읽는다.

```c
void MPU6050_Read_Accel(I2C_HandleTypeDef *hi2c, int16_t *ax, int16_t *ay, int16_t *az)
{
    uint8_t rec_data[6];
    HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x3B, 1, rec_data, 6, 1000);

    *ax = (int16_t)(rec_data[0] << 8 | rec_data[1]);
    *ay = (int16_t)(rec_data[2] << 8 | rec_data[3]);
    *az = (int16_t)(rec_data[4] << 8 | rec_data[5]);
}

void MPU6050_Read_Gyro(I2C_HandleTypeDef *hi2c, int16_t *gx, int16_t *gy, int16_t *gz)
{
    uint8_t rec_data[6];
    HAL_I2C_Mem_Read(hi2c, MPU6050_ADDR, 0x43, 1, rec_data, 6, 1000);

    *gx = (int16_t)(rec_data[0] << 8 | rec_data[1]);
    *gy = (int16_t)(rec_data[2] << 8 | rec_data[3]);
    *gz = (int16_t)(rec_data[4] << 8 | rec_data[5]);
}
```

#### 4.1.3 축 리맵

IMU의 장착 방향에 따라 가속도/자이로 축을 차량 좌표계로 변환하기 위해 `Remap_Axis` 함수를 사용한다. 이 함수는 `freertos.c`에 정의되어 있으며, 컴파일 타임 상수 `MOUNT_TYPE`에 따라 동작이 달라진다.

```c
void Remap_Axis(int16_t rx, int16_t ry, int16_t rz, int16_t *ox, int16_t *oy, int16_t *oz)
{
#if (MOUNT_TYPE == 1)
    *ox = -ry;
    *oy = rx;
    *oz = rz;

#elif (MOUNT_TYPE == 2)
    *ox = -ry;
    *oy = -rz;
    *oz = rx;

#endif
}
```

#### 4.1.4 Offset 보정

`main.h`에서 MOUNT_TYPE에 따라 적용할 오프셋 상수를 정의한다. ControlTask에서는 리맵된 값에서 해당 오프셋을 빼서 Zero-offset 보정을 수행한다.

```c
#define MOUNT_TYPE  1   // 1 or 2

#define OFFSET_AX_TYPE_1    -250
#define OFFSET_AY_TYPE_1    -2400
#define OFFSET_AZ_TYPE_1    -6000
#define OFFSET_GX_TYPE_1    -200
#define OFFSET_GY_TYPE_1    -840
#define OFFSET_GZ_TYPE_1    40

#define OFFSET_AX_TYPE_2    -2700
#define OFFSET_AY_TYPE_2    18000
#define OFFSET_AZ_TYPE_2    3000
#define OFFSET_GX_TYPE_2    -300
#define OFFSET_GY_TYPE_2    400
#define OFFSET_GZ_TYPE_2    -950
```

ControlTask 내에서는 다음과 같이 사용한다.

```c
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
```

---

### 4.2 초음파 거리 센서 (TIM4 Input Capture)

초음파 센서는 TRIG 핀을 짧게 High로 올린 뒤, ECHO 핀에서 High 구간의 길이를 측정하는 방식으로 동작한다. 본 프로젝트에서는 TIM4 CH2 Input Capture를 이용하여 상승엣지와 하강엣지 사이의 카운트 차이로 시간을 구하고, 이를 거리로 변환한다.

#### 4.2.1 타이머 캡처 콜백

`HAL_TIM_IC_CaptureCallback`에서 다음과 같이 구현한다.

1. 상승엣지에서 첫 번째 캡처 값(ic_val1)을 저장하고, 다음 인터럽트를 하강엣지로 설정한다.
2. 하강엣지에서 두 번째 캡처 값(ic_val2)을 읽고, 두 값의 차이를 계산한다.
3. `difference / 58`을 통해 거리(cm)를 계산하여 `g_distance`에 저장한다.

```c
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM4)
    {
        if (is_first_captured == 0)
        {
            ic_val1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
            is_first_captured = 1;
            __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_FALLING);
        }
        else
        {
            ic_val2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);

            if (ic_val2 > ic_val1)
            {
                difference = ic_val2 - ic_val1;
            }
            else
            {
                difference = (0xFFFF - ic_val1) + ic_val2;
            }

            g_distance = difference / 58;

            is_first_captured = 0;
            __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_RISING);
        }
    }
}
```

#### 4.2.2 TRIG 펄스 출력

ControlTask에서 초음파 측정을 위해 TRIG 핀을 짧게 High로 토글한다.

```c
HAL_GPIO_WritePin(US_TRIG_GPIO_Port, US_TRIG_Pin, GPIO_PIN_SET);
// 매우 짧은 지연 (for-loop)
for (int i = 0; i < 72 * 10; i++) __NOP();
HAL_GPIO_WritePin(US_TRIG_GPIO_Port, US_TRIG_Pin, GPIO_PIN_RESET);
```

---

## 5. 모터 및 서보 제어 (MotorHat / PCA9685)

MotorHat은 PCA9685 기반 I2C PWM 확장 모듈이다. `motorhat.c`에서 PCA9685 레지스터 접근을 추상화하고 서보/모터 제어 함수를 제공한다.

### 5.1 내부 헬퍼 함수

- `write8(reg, value)`  
  지정 레지스터에 1바이트 쓰기

- `readU8(reg)`  
  레지스터에서 1바이트 읽기

- `setPWM(channel, on, off)`  
  개별 채널의 ON/OFF 카운트 설정

- `setAllPWM(on, off)`  
  모든 채널 일괄 설정

### 5.2 PWM 주파수 설정

PCA9685의 출력 PWM 주파수를 설정하기 위해 `setPWMFreq(int freq)`를 사용한다. 25MHz 오실레이터 기준 prescale을 계산한 뒤 SLEEP 모드로 전환 → prescale 기록 → 재시작 순으로 동작한다.

```c
static void setPWMFreq(int freq)
{
    float prescaleval = 25000000.0;
    prescaleval /= 4096.0;
    prescaleval /= (float)freq;
    prescaleval -= 1.0;

    int prescale = (int)(prescaleval + 0.5);

    uint8_t oldmode = readU8(__MODE1);
    uint8_t newmode = (oldmode & 0x7F) | 0x10;   // sleep

    write8(__MODE1, newmode);
    write8(__PRESCALE, (uint8_t)prescale);
    write8(__MODE1, oldmode);

    HAL_Delay(5);
    write8(__MODE1, oldmode | 0x80);    // restart
}
```

초기화 함수 `MotorHat_Init()`에서는 전체 PWM을 초기화하고, MODE1/MODE2를 설정한 뒤 60Hz로 설정한다.

```c
void MotorHat_Init(void)
{
    setAllPWM(0, 0);
    write8(__MODE2, __OUTDRV);
    write8(__MODE1, __ALLCALL);
    HAL_Delay(5);

    uint8_t mode1 = readU8(__MODE1);
    mode1 = mode1 & ~__SLEEP;
    write8(__MODE1, mode1);
    HAL_Delay(5);

    setPWMFreq(60);
}
```

### 5.3 서보 조향 제어

서보는 PCA9685의 채널 0(PIN_SERVO)로 연결되어 있다. 입력 범위는 -100(좌) ~ +100(우)이고, 중앙은 0이다. 테스트 결과를 기반으로 다음과 같이 매핑한다.

- Left: 580
- Mid: 430
- Right: 280

이를 만족하는 선형식은 다음과 같다.

```c
// y = 430 - 1.5 * angle
int pwm_val = 430 - (int)(angle * 1.5f);
```

Motor_SetSteer 구현은 다음과 같다.

```c
void Motor_SetSteer(int16_t angle)
{
    if (angle < -100) angle = -100;
    if (angle > 100) angle = 100;

    int pwm_val = 430 - (int)(angle * 1.5f);
    setPWM(PIN_SERVO, 0, pwm_val);
}
```

### 5.4 DC 모터 스로틀 제어

DC 모터는 다음 채널 구성을 사용한다.

- PWM: 채널 13
- IN1: 채널 12
- IN2: 채널 11

입력 speed는 -100 ~ +100 범위이며, 다음과 같이 처리한다.

1. `abs(speed) * 4095 / 100` 으로 PWM 듀티 계산
2. speed > 0: 전진 (IN1 High, IN2 Low)
3. speed < 0: 후진 (IN1 Low, IN2 High)
4. speed = 0: 정지 (IN1/IN2 모두 OFF, PWM 0)

```c
void Motor_SetThrottle(int16_t speed)
{
    if (speed < -100) speed = -100;
    if (speed > 100) speed = 100;

    int pwm_val = abs(speed) * 4095 / 100;

    if (speed > 0)
    {
        setPWM(PIN_IN1, 0, 4096);
        setPWM(PIN_IN2, 4096, 0);
        setPWM(PIN_PWM, 0, pwm_val);
    }
    else if (speed < 0)
    {
        setPWM(PIN_IN1, 4096, 0);
        setPWM(PIN_IN2, 0, 4096);
        setPWM(PIN_PWM, 0, pwm_val);
    }
    else
    {
        setPWM(PIN_IN1, 0, 4096);
        setPWM(PIN_IN2, 0, 4096);
        setPWM(PIN_PWM, 0, 4096);
    }
}
```

---

## 6. FreeRTOS 기반 태스크 구조

본 프로젝트는 CMSIS-RTOS v2 래퍼를 사용하는 FreeRTOS를 기반으로 한다. 주요 OS 객체는 `freertos.c`에서 생성한다.

### 6.1 Mutex 및 Queue

- `stateMutex`  
  RcCarState_t 공유 데이터 보호용 뮤텍스

- `cmdQueue`  
  추후 확장용 명령 큐(현재는 직접 파싱 후 상태에 반영)

### 6.2 Task 요약

| Task 이름     | 주기 / 형태 | 우선순위 | 주요 기능                             |
| ------------- | ----------- | -------- | ------------------------------------- |
| DefaultTask   | 1000 ms     | Low      | Background                            |
| ControlTask   | 20 ms       | Realtime | 센서 읽기, 보정, Fail-safe, 모터 제어 |
| TelemetryTask | 50 ms       | Normal   | `$TEL` 텔레메트리 송신                |
| CommRxTask    | 이벤트 기반 | High     | `$CMD` 수신 처리                      |

### 6.3 ControlTask

ControlTask는 주로 다음과 같은 순서로 동작한다.

1. MPU6050 Accel/Gyro 읽기
2. 축 리맵 및 Offset 보정
3. 초음파 TRIG 펄스 출력
4. `g_distance` 값을 포함한 센서 데이터를 `g_carState`에 반영
5. 현재 throttle/steer 목표값을 `g_carState`에서 읽어온다.
6. Fail-safe 로직 적용(전방 10cm 이내 장애물 시 강제 정지)
7. MotorHat을 통해 서보/모터 PWM을 설정
8. 20ms 주기로 osDelay(20) 호출

뮤텍스는 다음과 같이 사용한다.

```c
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
```

Fail-safe는 다음과 같이 구현한다.

```c
if (g_distance > 0 && g_distance < 10 && target_thr > 0)
{
    target_thr = 0;
}
```

### 6.4 TelemetryTask

TelemetryTask는 약 50ms마다 다음 처리를 수행한다.

1. Mutex를 통해 `g_carState`를 로컬 변수로 복사한다.
2. `$TEL` 형식에 맞게 문자열을 구성한다.
3. UART DMA를 이용해 전송한다.

패킷 포맷은 명세서와 동일하다.

```c
int len = sprintf(tx_buffer, "$TEL,%d,%d,%d,%d,%d,%d,%lu,%d,%d
",
        current_state.ax, current_state.ay, current_state.az,
        current_state.gx, current_state.gy, current_state.gz,
        current_state.distance_cm,
        current_state.throttle, current_state.steer);
HAL_UART_Transmit_DMA(&huart1, (uint8_t *)tx_buffer, len);
```

### 6.5 CommRxTask

CommRxTask는 UART Idle 이벤트에 의해 깨워지는 태스크이다.

1. `HAL_UARTEx_RxEventCallback`에서 수신이 완료되면 `osThreadFlagsSet`으로 CommRxTask에 플래그를 전달한다.
2. CommRxTask는 `osThreadFlagsWait(0x01, ...)`로 대기하다가 데이터가 도착하면 깨어난다.
3. 수신된 버퍼를 문자열로 복사한 뒤 `strtok`를 이용해 파싱한다.
4. 첫 토큰이 `$CMD`인 경우, 두 번째와 세 번째 토큰을 각각 throttle, steer 값으로 해석하여 `g_carState`에 반영한다.

```c
if (!strcmp(token, "$CMD"))
{
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
```

---

## 7. UART DMA 통신 구조

### 7.1 Rx 처리 흐름

1. 초기화 단계에서 `HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buffer, RX_BUFFER_SIZE)` 를 호출하여 DMA 기반 수신을 시작한다.
2. 데이터가 도착하고 Idle Line이 감지되면 `HAL_UARTEx_RxEventCallback`이 호출된다.
3. 콜백에서 수신된 실제 길이(Size)를 확인하고 문자열 끝에 NULL 문자를 삽입한다.
4. CommRxTask에 스레드 플래그를 설정하여 새로운 명령이 도착했음을 알린다.
5. DMA 수신을 다시 시작한다.

```c
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
    if (huart->Instance == USART1)
    {
        if (Size < RX_BUFFER_SIZE)
            rx_buffer[Size] = ' ';
        else
            rx_buffer[RX_BUFFER_SIZE - 1] = ' ';

        if (CommRxTaskHandle != NULL)
        {
            osThreadFlagsSet(CommRxTaskHandle, 0x01);
        }

        HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buffer, RX_BUFFER_SIZE);
    }
}
```

### 7.2 UART 에러 처리

`HAL_UART_ErrorCallback`에서는 오버런, 노이즈, 프레이밍 에러 플래그를 클리어한 뒤 다시 `ReceiveToIdle_DMA`를 호출하여 RX 스트림을 복구한다. 이를 통해 장시간 운용 시에도 통신이 멈추지 않도록 한다.

```c
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        __HAL_UART_CLEAR_OREFLAG(huart);
        __HAL_UART_CLEAR_NEFLAG(huart);
        __HAL_UART_CLEAR_FEFLAG(huart);

        HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buffer, RX_BUFFER_SIZE);
    }
}
```

### 7.3 Uplink 패킷 ($TEL)

TelemetryTask에서 생성하는 `$TEL` 패킷은 명세서의 Uplink 메시지 정의와 1:1 대응한다.

```text
$TEL,AX,AY,AZ,GX,GY,GZ,DIST,THROTTLE,STEER
```

- AX, AY, AZ: 보정된 가속도 값
- GX, GY, GZ: 보정된 자이로 값
- DIST: 초음파 거리(cm)
- THROTTLE: 현재 스로틀 값(-100~100)
- STEER: 현재 스티어링 값(-100~100)

### 7.4 Downlink 패킷 ($CMD)

Downlink 명령은 `$CMD,THROTTLE,STEER` 형식을 따른다. RPi 측에서 이 문자열을 UART로 송신하면, CommRxTask에서 파싱 후 `g_carState`에 적용한다. 다음 ControlTask 주기부터 해당 값이 즉시 모터/서보 제어에 반영된다.

---

## 8. Fail-Safe 동작

명세서의 안전 요구 사항을 반영하여, 전방 장애물이 일정 거리 이내에 위치할 경우 차량을 강제 정지하도록 구현한다.

조건:

- `g_distance > 0`
- `g_distance < 10` (10cm 이내)
- `target_thr > 0` (전진 중)

위 조건을 모두 만족하면 `target_thr = 0`으로 변경하여 MotorHat에 전달하는 실제 스로틀 값이 0이 되도록 한다. 이 로직은 ControlTask 내부에 포함된다.

이는 실시간 안전 제어(Safety 기능)로서, 상위 계층(L2/L3)의 AI 로직과 무관하게 L1에서 즉시 반응할 수 있는 최종 방어선 역할을 한다.

---

## 9. 명세서 대비 구현 매핑

아래 표는 서비스/프로토콜 명세서상의 요구사항이 실제 코드에서 어떻게 구현되었는지 정리한 것이다.

| 명세서 요구사항                                   | 구현 내용                                             | 파일       |
| ------------------------------------------------- | ----------------------------------------------------- | ---------- |
| L1은 실시간 IMU·초음파 센서 수집                  | MPU6050_Read_Accel/Gyro, TIM4 Input Capture 기반 구현 | main.c     |
| 조향 및 스로틀 제어                               | Motor_SetSteer, Motor_SetThrottle 함수                | motorhat.c |
| `$TEL` 텔레메트리 전송                            | TelemetryTask에서 50ms 간격으로 sprintf + DMA 전송    | freertos.c |
| `$CMD` 주행 명령 수신                             | CommRxTask에서 UART DMA 수신 버퍼 파싱                | freertos.c |
| 센서 축 리맵 적용                                 | Remap_Axis 함수로 차량 좌표계 기준으로 변환           | freertos.c |
| Zero-offset 보정                                  | main.h의 OFFSET\_\* 매크로 사용                       | main.h     |
| 전방 거리 기반 Fail-safe                          | ControlTask 내부 거리 조건 체크 후 스로틀 0으로 설정  | freertos.c |
| UART DMA 기반 신뢰성 높은 통신 구조               | ReceiveToIdle_DMA + RxEventCallback + ErrorCallback   | main.c     |
| 하드 실시간 제어를 위한 태스크 주기(20ms/50ms 등) | osDelay 기반 고정 주기 Task                           | freertos.c |

---

## 10. 전체 동작 흐름 요약

전체 펌웨어의 실행 흐름은 다음과 같다.

1. 시스템 초기화 단계에서 클럭, GPIO, I2C, UART, TIM, DMA를 초기화한다.
2. MPU6050을 초기화하고, 초음파 타이머(TIM4 Input Capture)를 시작한다.
3. UART1 RX를 DMA + Idle 모드로 시작한다.
4. FreeRTOS 커널을 시작하면 각 Task가 지정된 스케줄에 따라 동작한다.
5. ControlTask는 20ms 주기로 센서 데이터를 읽고, 보정 및 Fail-safe 적용 후 MotorHat으로 모터/서보를 제어한다.
6. TelemetryTask는 50ms 주기로 `g_carState`를 기반으로 `$TEL` 패킷을 UART DMA로 송신한다.
7. 외부(RPi)에서 `$CMD` 패킷을 전송하면 UART Idle 인터럽트 → CommRxTask 실행 → throttle/steer 갱신 흐름을 거쳐 다음 제어 주기부터 바로 반영된다.
8. 운행 중 에러가 발생하여 UART 수신이 멈출 경우, ErrorCallback에서 플래그를 클리어하고 DMA 수신을 재시작한다.

---

## 11. 결론

본 STM32 L1 펌웨어는 명세서에서 정의된 제어 기능을 충실하게 반영하고 있으며 다음과 같은 특성을 가진다.

1. FreeRTOS 기반 스케줄링과 DMA/타이머 인터럽트를 활용하여 하드 실시간에 가까운 제어를 수행한다.
2. MPU6050 및 초음파 센서 데이터를 주기적으로 수집하고, 축 리맵 및 Offset 보정을 통해 차량 좌표계 기준의 안정적인 데이터를 제공한다.
3. PCA9685 기반 MotorHat을 사용하여 서보 조향과 DC 모터 속도를 정밀하게 제어한다.
4. UART DMA + Idle Line 인터럽트 + 에러 복구 로직을 통해 신뢰성 높은 양방향 통신 채널을 구현한다.
5. `$TEL` 텔레메트리 패킷을 통해 상위 계층(L2/L3)에서 AI 예지 정비(PdM) 알고리즘과 안전 분석에 활용할 수 있는 풍부한 데이터를 제공한다.
6. 전방 거리 기반 Fail-safe 로직을 L1에 내장함으로써, 상위 계층의 장애 또는 지연과 무관하게 최소한의 안전 기능을 보장한다.
7. 코드 구조가 Task, 드라이버, 유틸리티 레벨로 분리되어 있어 향후 PID 제어, 추가 센서, `$TUN` 기반 튜닝 파라미터 적용 등 기능 확장이 용이하다.

이 문서는 프로젝트 산출물로써 L1 제어 계층의 기술적 구현 내용을 정리하고, 상위 계층과의 연동 및 예지 정비, 자율주행 기능 개발의 기반이 되는 펌웨어 구조를 설명한다.
