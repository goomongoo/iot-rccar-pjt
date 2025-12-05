# STM32 RC Car Firmware (L1 Control Layer)

본 문서는 AI 예지 정비 및 사람 추종 자율주행 RC Car 프로젝트의 L1(STM32) 펌웨어 기능을 요약한 기술 문서이다.

---

# 1. 시스템 개요

L1 제어 계층은 다음 기능을 수행한다.

- MPU6050 가속도/자이로 수집
- 초음파 거리 측정(TIM4 Input Capture)
- 서보/모터 제어(PCA9685 MotorHat)
- 실시간 Fail-safe 제어(전방 장애물 감지 시 정지)
- 텔레메트리 `$TEL` 주기 전송
- `$CMD` 명령 수신 처리
- FreeRTOS 기반 스케줄링(Control/Telemetry/CommRx)

---

# 2. 코드 구조

```
/Core
 ├── Inc/main.h
 ├── Inc/motorhat.h
 ├── Src/main.c
 ├── Src/freertos.c
 └── Src/motorhat.c
```

- main.c: MCU 초기화, MPU6050/Ultrasonic/Rx-DMA 구성
- freertos.c: Task, Mutex 생성 및 주요 제어 루프
- motorhat.c: PCA9685 기반 PWM·서보·모터 제어

---

# 3. RC Car 상태 구조체

```c
typedef struct {
    int16_t ax, ay, az;
    int16_t gx, gy, gz;
    uint32_t distance_cm;
    int16_t throttle;
    int16_t steer;
} RcCarState_t;
```

FreeRTOS Mutex로 보호되며 ControlTask·TelemetryTask·CommRxTask에서 공유된다.

---

# 4. 센서 입력 처리 요약

- MPU6050: I2C로 6바이트씩 읽어 accel/gyro 획득
- 장착 방향 보정: Remap_Axis()
- Zero-offset 적용: main.h의 OFFSET 값 사용
- 초음파: TIM4 입력 캡처 상승→하강 시간 측정 후 distance = pulse/58 계산

---

# 5. MotorHat(PCA9685) 제어 요약

## 5.1 PWM 설정

- prescale 계산 후 60 Hz 설정
- setPWM(channel, on, off)로 PWM 출력 제어

## 5.2 Steering

- 입력: -100 ~ +100
- PWM 매핑: `pwm = 430 - 1.5 * angle`

## 5.3 Throttle

- PWM = `abs(speed) * 4095 / 100`
- IN1/IN2 조합으로 전진/후진/정지 제어

---

# 6. FreeRTOS Task 구조

| Task          | 주기        | 역할                                                  |
| ------------- | ----------- | ----------------------------------------------------- |
| ControlTask   | 20 ms       | 센서 읽기, 오프셋/리맵 적용, Fail-safe, MotorHat 제어 |
| TelemetryTask | 50 ms       | `$TEL` 전송                                           |
| CommRxTask    | 이벤트 기반 | `$CMD` 파싱 및 상태 갱신                              |

---

# 7. UART DMA 통신 구조 요약

- DMA 기반 ReceiveToIdle 방식 사용
- Idle 인터럽트 발생 시 RxEventCallback → CommRxTask로 전달
- `$CMD,THR,STR` 파싱하여 throttle/steer 갱신
- `$TEL` 패킷은 DMA로 반복 전송

---

# 8. Fail-safe 로직

조건: 전방 거리 < 10 cm AND throttle > 0  
→ throttle = 0 강제 적용하여 충돌 방지

---

# 9. 명세서 대비 구현 매핑 요약

| 요구사항        | 구현 파일  |
| --------------- | ---------- |
| 센서 수집       | main.c     |
| 모터/서보 제어  | motorhat.c |
| 태스크 스케줄링 | freertos.c |
| 텔레메트리      | freertos.c |
| 명령 수신       | freertos.c |
| Fail-safe       | freertos.c |

---

# 10. 전체 동작 흐름 요약

1. MCU 및 주변장치 초기화
2. MPU6050·Ultrasonic 시작
3. UART DMA 수신 시작
4. FreeRTOS Scheduler 시작
5. ControlTask: 센서 처리 + 모터 제어
6. TelemetryTask: 주기적 `$TEL` 송신
7. CommRxTask: `$CMD` 수신 및 갱신

---

# 11. 결론

L1 펌웨어는 실시간 제어를 위해 FreeRTOS, DMA, 타이머 캡처를 결합하여 안정적으로 동작하며, 상위 계층(L2/L3)의 AI·관제 시스템이 활용할 수 있는 핵심 센서·제어 데이터를 제공한다. 구조가 명확하며 향후 PID 추가, 더 많은 센서 확장, 튜닝 명령 `$TUN` 지원 등이 용이하도록 설계되어 있다.
