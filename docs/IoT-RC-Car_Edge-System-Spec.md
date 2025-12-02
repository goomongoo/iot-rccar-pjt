# 관통 PJT 기획서 + 프로토콜 명세서
문서 버전: 2.3  
수정일: 2025.12.02  
프로젝트명: **AI 예지 정비(PdM) 및 사람 추종 자율주행 RC Car**

---

# Part 1. 서비스 기획서

## 1. 서비스 개요

### 서비스 기본 정보

| 항목 | 내용 |
|------|------|
| **서비스명** | AI 예지 정비(PdM) 기능이 탑재된 하이브리드 실시간 제어 아키텍처 |
| **서비스 개요** | STM32 Nucleo 기반 Hard RT 제어 + RPi 5 기반 AI 분석/GUI의 역할을 분리한 3계층 구조. RC카의 Steering/Throttle 입력과 IMU 반응을 실시간 분석하여 ‘현재 사고’와 ‘미래 고장 징후’를 모두 탐지하는 시스템 |
| **핵심 기능** | ① 하이브리드 제어 아키텍처 ② 실시간 이상 징후 감지 ③ 예지 정비(PdM) ④ 실시간 튜닝 GUI |

---

### 계층별 기능 요약

| 계층 | 하드웨어 | 역할 | 실시간성 |
|------|---------|------|----------|
| **L1 – 제어 계층** | STM32 Nucleo-F103RB | 모터 제어, 서보 조향, IMU·초음파 센서 수집 | **Hard Real-Time** |
| **L2 – 엣지/비전 계층** | Raspberry Pi 4 | 게이트웨이(UART↔MQTT), 카메라 처리 | Soft RT |
| **L3 – 관제/AI 계층** | Raspberry Pi 5 | AI 분석, 예지 정비, GUI | Soft RT |

---

### 실시간 AI 이상 징후 감지

| 항목 | AI 기능 1 (Safety) | AI 기능 2 (PdM) |
|------|---------------------|----------------|
| **기능명** | 실시간 전복·충돌 감지 | 예지 정비(Predictive Maintenance) |
| **설명** | IMU·초음파 기반 사고 즉시 감지 | 입력(Throttle·Steer) 대비 출력(IMU) 기반 고장 징후 예측 |
| **활용 데이터** | Accel/Gyro/Distance | Accel/Gyro + Steering/Throttle |
| **예측 로직** | Rule-based 즉시 탐지 | LSTM/AE 기반 정상패턴 대비 이상 탐지 |

---

# Part 2. 통신 프로토콜 명세서

## 1. 하드웨어 구성 개요

| 계층 | 구성 요소 | 설명 |
|------|-----------|------|
| **L1** | STM32 Nucleo-F103RB + MotorHat(I2C) | 제어 및 센서 |
| **L2** | Raspberry Pi 4 | Camera / UART–MQTT Gateway |
| **L3** | Raspberry Pi 5 | AI / GUI / Logging |

---

## 2. L1 ↔ L2 물리 계층 (UART)

| 항목 | 값 |
|------|-----|
| **통신 방식** | UART (Async Serial) |
| **Baud Rate** | 115200 |
| **Data Bits** | 8 |
| **Stop Bits** | 1 |
| **Parity** | None |
| **전압 레벨** | 3.3V TTL |

### 핀 매핑

| STM32 | Raspberry Pi |
|-------|--------------|
| PA2 (TX) | GPIO 15 (RX) |
| PA3 (RX) | GPIO 14 (TX) |
| GND | GND |

---

## 3. 데이터 링크 계층 – 프레임 포맷

| 항목 | 값 |
|------|--------|
| **헤더** | `$` |
| **구분자** | `,` |
| **종료문자** | `\n` |
| **형식** | `$PacketID, Payload1,...PayloadN\n` |

---

## 4. Uplink 메시지 (STM32 → RPi4 → RPi5)

### 4.1 `$TEL` 텔레메트리 (20Hz)

```
$TEL, AX, AY, AZ, GX, GY, GZ, DIST, THROTTLE, STEER
```

| IDX | 항목 | 타입 | 단위/범위 | 설명 | PdM 활용 |
|-----|------|-------|------------|--------|-----------|
| 0 | PacketID | String | `$TEL` | 패킷 식별자 | - |
| 1 | AX | Int16 | Raw | 가속도 X | 구동 반응도 |
| 2 | AY | Int16 | Raw | 가속도 Y | 코너 쏠림 |
| 3 | AZ | Int16 | Raw | 가속도 Z | 노면/진동 |
| 4 | GX | Int16 | Raw | 자이로 X | - |
| 5 | GY | Int16 | Raw | 자이로 Y | - |
| 6 | GZ | Int16 | Raw | 자이로 Z(Yaw) | 조향 반응 |
| 7 | DIST | UInt16 | cm | 전방 거리 | 충돌 경고 |
| 8 | THROTTLE | Int16 | -100~100 | DC모터 출력 | 입력 신호 |
| 9 | STEER | Int16 | -100~100 | 서보 조향 | 입력 신호 |

---

### 4.2 `$STS` 시스템 상태 메시지

```
$STS, CODE, MESSAGE
```

| 항목 | 값 |
|------|------|
| CODE | 0=Info, 1=Warn, 2=Error, 99=Fatal |
| MESSAGE | 오류 내용 문자열 |

예시:  
`$STS, 99, COLLISION_DETECTED`

---

## 5. Downlink 메시지 (RPi5 → RPi4 → STM32)

### 5.1 `$CMD` — 주행 제어 명령

```
$CMD, THROTTLE, STEER
```

| 항목 | 범위 | 설명 |
|------|--------|--------|
| THROTTLE | -100~+100 | 전진(+) 후진(-) |
| STEER | -100~+100 | 좌(-) 우(+) |

---

### 5.2 `$TUN` — 튜닝 파라미터 설정

```
$TUN, TYPE, VALUE
```

| TYPE | 설명 |
|------|------|
| 1 | Servo Trim |
| 2 | Gyro Zero Offset |

---

## 6. MQTT Topic 맵핑 (L2 ↔ L3)

| Topic | 방향 | 설명 | 매핑되는 UART |
|--------|--------|---------|---------------|
| mobility/telemetry/raw | L2 → L3 | 텔레메트리 데이터 | `$TEL` |
| mobility/alert/event | L2 → L3 | 사고·오류 이벤트 | `$STS` |
| mobility/control/drive | L3 → L2 | 주행 명령 | `$CMD` |
| mobility/admin/tuning | L3 → L2 | 파라미터 설정 | `$TUN` |

---

## 7. 주요 시나리오

### A. 예지 정비(PdM)

| 단계 | 설명 |
|------|------|
| 1 | L3에서 패턴 명령 전송 |
| 2 | L1 모터/서보 제어 |
| 3 | L1이 20Hz 텔레메트리 전송 |
| 4 | L3가 입력 vs IMU 패턴 분석 |
| 5 | 이상 징후 판단 |

---

### B. 직진 보정(Heading Assist)

| 조건 | 동작 |
|------|------|
| STEER=0 | Yaw 변화 시 반대 방향 미세 조향하여 직진 유지 |

---


