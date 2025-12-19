# 데이터 수집 스크립트 README (collect.sh 기반)

본 도구는 RPi5(또는 PC)에서 **MQTT로 주행 명령을 발행**하고,
동시에 **텔레메트리(topic: `mobility/telemetry/parsed`)를 구독하여 CSV로 저장**하는 데이터 수집 스크립트이다.

⚠️ **데이터 수집은 반드시 `collect.sh`를 통해서만 수행한다.**
`collect.py`는 내부 실행용 헬퍼 스크립트이며, 직접 실행하지 않는다.

---

## 1) 전제 조건 (시스템/토픽)

### MQTT 브로커

* 브로커: `RPi5 IP주소`
* 포트: `1883`

### 사용 토픽

* **명령 발행(topic)**: `mobility/control/drive` (qos=1)
  payload(JSON):

  ```json
  {"throttle": <int>, "steer": <int>}
  ```

* **텔레메트리 구독(topic)**: `mobility/telemetry/parsed` (qos=1)

> RPi4 브리지 또는 MCU가 위 토픽으로 데이터를 송수신하고 있어야 정상적으로 수집된다.

---

## 2) 설치 / 실행 준비

### Python 패키지

```bash
pip install paho-mqtt
```

### 실행 권한 부여

```bash
chmod +x collect.sh
```

---

## 3) 시나리오 이름 규칙 (필수)

CSV 파일명은 **주행 방향 + 조향 상태**를 명확히 표현하도록
아래 규칙을 **반드시 따른다**.

### 기본 형식

```
<direction>_<steer>.csv
<steer>_idle.csv
idle.csv
```

* 소문자 사용
* 단어 구분은 `_`
* 확장자는 `.csv`

---

### 시나리오 정의

#### ① 정지 계열

| 파일명                    | 의미                  |
| ---------------------- | ------------------- |
| `idle.csv`             | throttle=0, steer=0 |
| `steer_left_idle.csv`  | throttle=0, steer<0 |
| `steer_right_idle.csv` | throttle=0, steer>0 |

#### ② 전진 계열

| 파일명                | 의미       |
| ------------------ | -------- |
| `fwd_straight.csv` | 전진 + 직진  |
| `fwd_left.csv`     | 전진 + 좌회전 |
| `fwd_right.csv`    | 전진 + 우회전 |

#### ③ 후진 계열

| 파일명                | 의미       |
| ------------------ | -------- |
| `rev_straight.csv` | 후진 + 직진  |
| `rev_left.csv`     | 후진 + 좌회전 |
| `rev_right.csv`    | 후진 + 우회전 |

> 📌 **파일명 = state label**
> 이후 모든 분석, preset(p95), anomaly rule은 파일명을 기준으로 state를 구분한다.

---

## 4) collect.sh 사용법 (유일한 수집 방법)

### 사용 형식

```bash
./collect.sh <scenario> <throttle> <steer> <repeat>
```

* `scenario`

  * 위 시나리오 이름에서 **`.csv`를 제거한 문자열**
* `throttle`, `steer`

  * MQTT로 전송할 주행 명령 값
* `repeat`

  * 반복 수집 횟수

---

### 실행 예시 (권장)

```bash
# 정지
./collect.sh idle 0 0 20

# 조향만 (idle)
./collect.sh steer_left_idle 0 -60 20
./collect.sh steer_right_idle 0 60 20

# 전진
./collect.sh fwd_straight 60 0 50
./collect.sh fwd_left 60 -40 50
./collect.sh fwd_right 60 40 50

# 후진
./collect.sh rev_straight -60 0 50
./collect.sh rev_left -60 -40 50
./collect.sh rev_right -60 40 50
```

---

## 5) 동작 방식 요약

1. `ENTER` 입력 시 1회 수집 시작
2. 주행 명령 1회 MQTT publish
3. 고정 시간(`DURATION=2.0s`) 동안 텔레메트리 수집
4. 자동 정지 명령 전송
5. CSV 파일에 데이터 append
6. 지정한 횟수만큼 반복

* 중간 중단: `Ctrl+C` (현재 반복 횟수 출력 후 종료)

---

## 6) 출력 파일 구조

```text
data/train/
 ├─ idle.csv
 ├─ steer_left_idle.csv
 ├─ steer_right_idle.csv
 ├─ fwd_straight.csv
 ├─ fwd_left.csv
 ├─ fwd_right.csv
 ├─ rev_straight.csv
 ├─ rev_left.csv
 └─ rev_right.csv
```

---

## 7) CSV 포맷

```text
ts_ms, ax, ay, az, gx, gy, gz, dist_cm, throttle, steer
```

* 텔레메트리 JSON 필드를 그대로 CSV row로 저장
* 필드 누락 시 빈 값으로 기록

---

## 8) 자주 겪는 문제

* **CSV에 데이터가 안 쌓일 때**

  * `mobility/telemetry/parsed` 토픽 발행 여부 확인
  * 브로커 IP/포트 확인

* **차가 안 움직일 때**

  * `mobility/control/drive` 토픽 확인
  * throttle/steer 부호 방향 확인