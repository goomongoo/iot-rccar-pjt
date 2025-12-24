# GUI Remote Controller (L3)

본 모듈은 **관통 PJT – AI 예지 정비(PdM) 및 사람 추종 자율주행 RC Car**의
L3(관제/AI 계층)에 해당하는 **GUI 기반 원격 제어 및 이상 탐지 컨트롤러**이다.

PySide6(Qt)를 기반으로 한 GUI를 통해 RC Car를 직접 제어하고,
MQTT를 통해 실시간 텔레메트리를 수신하여 **AI 기반 이상 탐지 + Rule 기반 안전 로직**을 동시에 수행한다.
또한 모든 텔레메트리와 이상 이벤트는 **Firebase Firestore**로 업로드된다.

---

## 1. 주요 기능 요약

### 1.1 주행 제어 (GUI Controller)

* Throttle / Steer 기반 RC Car 원격 제어
* 지원 버튼

  * **Go**: 전진 (Throttle = +60)
  * **Back**: 후진 (Throttle = -60)
  * **Left / Right**: 조향
  * **Mid**: 조향 중립 (Steer = 0)
  * **BRAKE**: 즉시 정지 (Throttle = 0)
* **GUI 모드 / Gesture 모드 전환** 지원

### 1.2 MQTT 기반 실시간 통신

* 주행 명령 발행
* 텔레메트리 수신
* 상태 이벤트(US_BRAKE 등) 수신

### 1.3 AI 기반 이상 탐지 (Predictive Maintenance)

* TorchScript 시계열 예측 모델 사용
* **입력**: 과거 `T_IN=20` 프레임 (IMU + Throttle + Steer)
* **출력**: 미래 `T_OUT=20` 프레임 (IMU)
* **Anomaly Score**: 예측값 vs 실제값의 MSE 평균

### 1.4 상태별 Baseline 학습 + 적응

* 상태 분류: `idle / fwd / rev / turn`
* Burn-in 기반 초기 baseline 학습
* 안전 구간에서 EWMA 기반 threshold 적응
* 상태 전이, 브레이크, 비상정지 상황에서 **baseline 오염 방지 로직** 적용

### 1.5 Firestore 연동

* 1초 주기로 최신 텔레메트리 업로드
* 이상 탐지 발생 시 alert 컬렉션에 이벤트 기록
* 서버 시간 기준 타임스탬프 사용 (Asia/Seoul)

---

## 2. 실행 방법

### 2.1 필수 인자

MQTT Broker IP는 **반드시 실행 시 인자로 전달**해야 한다.
예시)

```bash
python main.py --broker 192.168.0.75
```

---

## 3. 시스템 아키텍처 내 위치

```
[ STM32 (L1) ]
   ↑  UART
[ RPi4 (L2) : UART ↔ MQTT Bridge ]
   ↑  MQTT
[ RPi5 (L3) : GUI Controller + AI ]
```

본 GUI는 **Soft Real-Time 계층**으로,
Hard RT 제어는 MCU(L1)에 위임하고
상태 해석·이상 판단·관제는 L3에서 수행한다.

---

## 4. UI 구성

* 고정 해상도: **800 × 600**
* 좌측: **Command Log**
* 우측: **Sensing / Anomaly Log**
* 하단: 주행 제어 버튼
* 상단: START / STOP 버튼

UI 정의 파일:

* `ui_form.py` 

---

## 5. MQTT 토픽 설계

| Topic                       | 방향       | 설명                  |
| --------------------------- | -------- | ------------------- |
| `mobility/control/drive`    | GUI → L2 | Throttle / Steer 제어 |
| `mobility/control/mode`     | GUI → L2 | GUI / Gesture 모드    |
| `mobility/telemetry/parsed` | L2 → GUI | 센서 텔레메트리            |
| `mobility/alert/event`      | L2 → GUI | US_BRAKE 등 상태 이벤트   |

MQTT 관리 모듈:

* `mqtt_manager.py` 

---

## 6. AI Predictor 구조

### 6.1 Predictor 개요

* TorchScript 모델 사용 (CPU/GPU 자동 선택)
* 센서 6축 + 명령 2축 = 총 8차원 입력
* Sliding Window + Stride 방식 추론

### 6.2 Anomaly Score 정의

```text
score = mean( (predicted_IMU - actual_IMU)^2 )
```

Predictor 구현:

* `predictor_engine.py` 
* 모델 파일: `predictor_ts.pt`
* 스케일러: `sensor_scaler.pkl`

---

## 7. Baseline & Alert 설계 철학

### 7.1 상태별 Baseline

* 상태별 독립 threshold 관리
* Burn-in (`N=60`) 후 baseline 확정
* `thr = μ + K·σ`

### 7.2 오염 방지 정책

* BRAKE 직후

  * **1.5s**: baseline 업데이트 금지
  * **1.0s**: alert mute
* Idle 진입 직후

  * **0.7s**: idle baseline freeze
* US_BRAKE 감지 시

  * baseline 업데이트 완전 차단

이 로직은
**“정상적 제어로 인한 급격한 가속 변화 ≠ 이상”** 이라는 가정을 기반으로 한다.

---

## 8. Firestore 연동

### 8.1 Telemetry 업로드

* 주기: 1초
* 컬렉션: `telemetry`

### 8.2 Alert 업로드

* 이벤트 발생 시 즉시 업로드
* 컬렉션: `alert`
* anomaly 발생 당시 텔레메트리 포함

Firebase 모듈:

* `firebase_uploader.py` 

---

## 9. 주요 파일 구조

```
.
├── main.py                 # Entry point (broker IP 필수)
├── mainwindow.py           # GUI + 전체 제어 로직
├── ui_form.py              # Qt UI 정의
├── mqtt_manager.py         # MQTT wrapper
├── predictor_engine.py     # AI 예측 엔진
├── predictor_ts.pt         # TorchScript 모델
├── sensor_scaler.pkl       # Sensor scaler
├── firebase_uploader.py    # Firestore 연동
├── config.py               # 시스템 설정
```

---

## 10. 설계 의도 요약

* **Hard RT 제어와 AI 관제를 명확히 분리**
* AI 단독 판단이 아닌 **Rule + Predictor 병행**
* Baseline은 “정답”이 아니라 **적응 가능한 안전 영역**
* GUI는 단순 조작 도구가 아니라
  **시스템 상태를 관찰·해석하는 관제 패널**
