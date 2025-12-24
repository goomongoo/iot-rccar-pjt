# MQTT ↔ UART Gateway (GUI / Gesture Dual Mode)

`gateway.py`는 Raspberry Pi 4 (L2 계층)에서 동작하는 **UART ↔ MQTT 브리지**로,
GUI 기반 제어와 **카메라 제스처 인식 기반 제어**를 **런타임 모드 전환**으로 지원합니다.

이 모듈은 STM32(L1)와 Raspberry Pi 5(L3) 사이의 **통신 허브** 역할을 수행합니다.

---

## 1. 역할 요약 (What this module does)

* **UART → MQTT**

  * STM32에서 수신한 `$TEL` 텔레메트리를 JSON으로 변환해 MQTT Publish
  * `$STS` 시스템 이벤트를 Alert 메시지로 변환하여 Publish
* **MQTT → UART**

  * GUI에서 전달된 주행 명령을 STM32 제어 명령 `$CMD`로 변환
  * 제스처 인식 결과를 주행 명령으로 변환하여 UART 전송
* **모드 전환**

  * `GUI` / `Gesture` 모드를 MQTT 토픽으로 실시간 전환

---

## 2. 시스템 내 위치 (관통 PJT 기준)

| 계층     | 장치                  | 역할                                  |
| ------ | ------------------- | ----------------------------------- |
| **L1** | STM32 Nucleo-F103RB | 모터/서보 제어, IMU·초음파 센서                |
| **L2** | Raspberry Pi 4      | **UART ↔ MQTT Gateway, Gesture 인식** |
| **L3** | Raspberry Pi 5      | GUI, AI 추론, 로깅, Firestore           |

---

## 3. 통신 구조 개요

### UART (L1 ↔ L2)

* Baudrate: **115200**
* Frame 형식:

  ```
  $CMD,THROTTLE,STEER
  $TEL,AX,AY,AZ,GX,GY,GZ,DIST,THROTTLE,STEER
  $STS,EVENT
  ```

### MQTT (L2 ↔ L3)

| Topic                       | Direction | 설명                           |
| --------------------------- | --------- | ---------------------------- |
| `mobility/control/mode`     | L3 → L2   | 제어 모드 전환 (`GUI` / `Gesture`) |
| `mobility/control/drive`    | L3 → L2   | GUI 기반 주행 명령                 |
| `mobility/telemetry/parsed` | L2 → L3   | 파싱된 텔레메트리                    |
| `mobility/alert/event`      | L2 → L3   | 시스템/안전 이벤트                   |

---

## 4. 제어 모드 (Control Modes)

### 4.1 GUI Mode (기본값)

* MQTT 토픽: `mobility/control/drive`
* JSON 형식:

  ```json
  {
    "throttle": 60,
    "steer": -20
  }
  ```
* 동작:

  ```
  MQTT → gateway.py → $CMD → STM32
  ```

### 4.2 Gesture Mode

* MediaPipe 기반 손 제스처 인식
* 인식 결과를 **Throttle / Steer 값으로 매핑**
* GUI 명령은 **무시됨**

#### Gesture Mapping

| Gesture     | Throttle | Steer |
| ----------- | -------- | ----- |
| Thumb_Up    | +60      | 0     |
| Thumb_Down  | -60      | 0     |
| Closed_Fist | 0        | 0     |
| Open_Palm   | 0        | 0     |
| Pointing_Up | 0        | -100  |
| Victory     | 0        | +100  |

---

## 5. 실행 방법

### 5.1 필수 조건

```bash
pip install pyserial paho-mqtt
```

Gesture 모드 사용 시:

```bash
pip install opencv-python mediapipe
```

---

### 5.2 실행

```bash
python gateway.py --broker 192.168.0.75
```

옵션:

```bash
--broker   MQTT 브로커 주소 (필수)
--port     MQTT 포트 (기본: 1883)
--serial   UART 디바이스 직접 지정 (선택)
```

예:

```bash
python gateway.py --broker 192.168.0.75 --serial /dev/ttyAMA0
```

---

## 6. UART 포트 자동 감지 전략

Raspberry Pi 4 / 5 환경 차이를 고려하여 **순차 탐색 방식**을 사용합니다.

```python
DEFAULT_SERIAL_CANDIDATES = [
    "/dev/serial0",
    "/dev/ttyAMA0",
    "/dev/ttyS0",
    "/dev/serial1",
]
```

* `--serial` 미지정 시 자동 탐색
* 지정했는데 실패하면 **즉시 종료 (fail-fast)**

---

## 7. 내부 구조 요약

### 주요 스레드

| Thread        | 역할                        |
| ------------- | ------------------------- |
| Main Thread   | UART 수신 → MQTT Publish    |
| MQTT Loop     | MQTT Subscribe / Callback |
| GestureWorker | 카메라 입력 + MediaPipe 추론     |

### 동시성 제어

* `uart_lock` : UART write 충돌 방지
* `mode_lock` : 제어 모드 경쟁 상태 방지