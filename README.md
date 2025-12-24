# IoT RC Car

본 프로젝트는 **STM32 기반의 하드 실시간(Hard RT) 제어**와 **Raspberry Pi 기반의 AI 분석 및 GUI**를 결합한 3계층 하이브리드 실시간 제어 아키텍처 시스템입니다. RC카의 주행 데이터를 20Hz 주기로 정밀하게 분석하여 전복, 충돌 등의 사고를 감지할 뿐만 아니라, AI 모델을 통해 정상 패턴에서 벗어난 미세한 징후를 찾아내는 **실시간 이상 탐지(Anomaly Detection)** 기능을 핵심으로 합니다.

## 1. 시스템 아키텍처

역할과 실시간성 요구사항에 따라 시스템을 3개의 계층으로 분리하여 안정성을 확보했습니다.

| 계층 | 장치 | 역할 | 실시간성 |
| --- | --- | --- | --- |
| **L1 – 제어 계층** | STM32 Nucleo-F103RB | 모터/서보 제어, 센서(IMU, 초음파) 데이터 수집 | **Hard Real-Time** |
| **L2 – 게이트웨이** | Raspberry Pi 4 | UART↔MQTT 브리지, 미디어파이프 기반 제스처 인식 | Soft Real-Time |
| **L3 – 관제/AI** | Raspberry Pi 5 | **실시간 이상 탐지 분석**, GUI 제어, Firebase 업로드 | Soft Real-Time |

---

## 2. 주요 기능

### 2.1. 실시간 제어 및 안전 (L1)

* **Fail-safe 로직**: 전방 10cm 이내 장애물 감지 시 스로틀을 즉시 0으로 강제 설정하여 충돌을 방지합니다.
* **FreeRTOS 기반 스케줄링**: 제어(20ms), 텔레메트리 전송(50ms) 등 작업을 Mutex로 보호하며 정교하게 처리합니다.

### 2.2. 지능형 제어 및 비전 (L2)

* **듀얼 제어 모드**: MQTT 명령을 통한 GUI 모드와 카메라 제스처 인식 모드를 런타임에 실시간으로 전환합니다.
* **제스처 맵핑**: 엄지 위(전진), 엄지 아래(후진), 주먹/손바닥(정지), 가위(우회전) 등 손동작으로 조종합니다.

### 2.3. 실시간 이상 탐지 및 관제 (L3)

* **AI 이상 탐지**: LSTM/AE 기반 TorchScript 모델을 사용하여 명령 입력 대비 차량의 물리적 반응(IMU) 패턴을 분석하고, 예측값과 실제값의 MSE 평균으로 **이상 점수(Anomaly Score)**를 산출합니다.
* **상태별 Baseline 학습**: `idle`, `fwd`, `rev`, `turn` 등 주행 상태별로 정상 범위를 학습하여 상황에 맞는 **적응형 임계값(Threshold)**을 적용합니다.
* **Cloud 연동**: 최신 텔레메트리와 이상 탐지 시 발생하는 alert 이벤트를 **Firebase Firestore**에 실시간으로 기록합니다.

---

## 3. 통신 프로토콜 명세

### 3.1. L1 ↔ L2 (UART)

* **설정**: 115200 bps, 8N1.
* **주요 메시지**:
* `$TEL`: 가속도, 자이로, 거리, 명령 상태 등 전체 텔레메트리 (20Hz).
* `$CMD`: 스로틀 및 조향 제어 명령.
* `$STS`: 시스템 상태 및 사고·오류 이벤트 알림.



### 3.2. L2 ↔ L3 (MQTT)

* **Topic 맵핑**:
* `mobility/telemetry/parsed`: 파싱 및 정제된 센서 데이터 (이상 탐지 입력용).
* `mobility/control/drive`: GUI 또는 제스처 기반 주행 명령.
* `mobility/alert/event`: 실시간 이상 탐지 결과 및 안전 이벤트 알림.



---

## 4. 설치 및 실행 방법

### L1 (STM32)

1. `firmware-stm32` 프로젝트를 STM32CubeIDE에서 로드합니다.
2. 빌드 후 Nucleo-F103RB 보드에 플래싱합니다.

### L2 (Raspberry Pi 4 - Gateway)

```bash
cd vision-gateway-rpi4
pip install pyserial paho-mqtt opencv-python mediapipe
python gateway.py --broker [RPi5_IP]

```

### L3 (Raspberry Pi 5 - GUI/AI)

```bash
cd control-ai-rpi5/gui-controller
pip install PySide6 paho-mqtt torch firebase-admin
python main.py --broker [RPi5_IP]

```

---

## 5. 데이터 수집 (Training Data)

이상 탐지 모델의 정교함을 위해 전용 스크립트로 상태별 데이터를 수집합니다.

* **실행**: `./collect.sh <scenario> <throttle> <steer> <repeat>`.
* **규칙**: 파일명은 `fwd_straight`, `rev_left`, `idle` 등 정해진 시나리오 라벨을 반드시 따라야 합니다.

---

## 6. 프로젝트 구조

* `/docs`: 기획서 및 상세 시스템 명세서.
* `/firmware-stm32`: L1 실시간 제어 펌웨어.
* `/vision-gateway-rpi4`: L2 통신 허브 및 제스처 인식 모듈.
* `/control-ai-rpi5`: L3 관제 GUI, 이상 탐지 엔진, 데이터 수집 도구.
* `/dashboard-web`: Vue 3 기반 실시간 웹 인포테인먼트 대시보드.