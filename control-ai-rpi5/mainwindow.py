import sys
import json
import time
from datetime import datetime
from collections import deque, defaultdict

import numpy as np
import pytz
import paho.mqtt.client as mqtt
import joblib
import torch

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QThread, Signal, Slot, QTimer

from ui_form import Ui_MainWindow

# ============================================================
# MQTT topics / broker
# ============================================================
BROKER_IP = "RPi5 IP Address"
BROKER_PORT = 1883

TOPIC_PUB_CONTROL   = "mobility/control/drive"
TOPIC_SUB_TELEMETRY = "mobility/telemetry/parsed"
TOPIC_SUB_STATUS = "mobility/alert/event"

# ============================================================
# Model artifact paths (Predictor)
# ============================================================
MODEL_TS_PATH = "./predictor_ts.pt"
SCALER_PATH   = "./sensor_scaler.pkl"

# new preset json (now includes p95/p90/p50/n/winsorize_q)
PRESET_P95_PATH = "./baseline_p95_preset.json"

# Predictor windowing
T_IN = 20
T_OUT = 20
INFER_STRIDE = 5

# cmd scaling (dataset convention)
THR_MIN, THR_MAX = -100.0, 100.0
STR_MIN, STR_MAX = -100.0, 100.0

# time
korea_timezone = pytz.timezone("Asia/Seoul")

# ============================================================
# Firebase
# ============================================================
import firebase_admin
from firebase_admin import credentials, firestore

FIREBASE_KEY_PATH = "./qt-gui-controller-db-key.json"

db = None
try:
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized")
except Exception as e:
    print("Firebase init failed:", e)


class TelemetryUploadThread(QThread):
    def __init__(self):
        super().__init__()
        self.running = True
        self.latest_data = None

    def update_data(self, data):
        self.latest_data = data

    def run(self):
        while self.running:
            time.sleep(1.0)
            if db and self.latest_data:
                try:
                    ts = datetime.now(korea_timezone).strftime("%Y-%m-%d %H:%M:%S")
                    payload = dict(self.latest_data)
                    payload["server_time"] = ts
                    db.collection("telemetry").document(ts).set(payload)
                except Exception as e:
                    print("Firebase upload error:", e)

    def stop(self):
        self.running = False


# ============================================================
# Predictor Engine
# ============================================================
class PredictorEngine:
    def __init__(
        self,
        model_path=MODEL_TS_PATH,
        scaler_path=SCALER_PATH,
        T_IN=T_IN,
        T_OUT=T_OUT,
        stride=INFER_STRIDE,
        device=None,
    ):
        self.T_IN = int(T_IN)
        self.T_OUT = int(T_OUT)
        self.stride = int(stride)

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = torch.jit.load(model_path, map_location=self.device)
        self.model.eval()

        scaler = joblib.load(scaler_path)
        self.sensor_mean = scaler.mean_[:6].astype(np.float32)
        self.sensor_std  = scaler.scale_[:6].astype(np.float32)

        self.x_buf = deque(maxlen=self.T_IN)
        self.pending = deque()
        self.step = 0

        with torch.no_grad():
            y = self.model(torch.zeros(1, self.T_IN, 8))
        if list(y.shape) != [1, self.T_OUT, 6]:
            raise RuntimeError(f"Predictor output shape mismatch: got {list(y.shape)}")

    @staticmethod
    def _scale_cmd(v, lo=-100.0, hi=100.0):
        return 2.0 * (v - lo) / (hi - lo) - 1.0

    def _scale_frame(self, data):
        sensor = np.array(
            [data["ax"], data["ay"], data["az"],
             data["gx"], data["gy"], data["gz"]],
            dtype=np.float32
        )
        sensor_s = (sensor - self.sensor_mean) / (self.sensor_std + 1e-6)

        thr_s = self._scale_cmd(float(data["throttle"]), THR_MIN, THR_MAX)
        str_s = self._scale_cmd(float(data["steer"]),    STR_MIN, STR_MAX)

        x = np.array([*sensor_s, thr_s, str_s], dtype=np.float32)
        return x, sensor_s

    @torch.no_grad()
    def _predict(self, x_seq):
        x = torch.from_numpy(x_seq[None]).to(self.device)
        y = self.model(x)
        return y.squeeze(0).cpu().numpy()

    def update(self, data):
        x_s, sensor_s = self._scale_frame(data)

        if self.pending:
            self.pending[0]["actual"].append(sensor_s)
            if len(self.pending[0]["actual"]) == self.T_OUT:
                pred = self.pending[0]["pred"]
                act  = np.stack(self.pending[0]["actual"])
                score = float(np.mean((pred - act) ** 2))
                self.pending.popleft()
                return score

        self.x_buf.append(x_s)
        self.step += 1

        if len(self.x_buf) == self.T_IN and (self.step % self.stride == 0):
            y_pred = self._predict(np.stack(self.x_buf))
            self.pending.append({"pred": y_pred, "actual": []})

        return None

    def reset(self):
        self.x_buf.clear()
        self.pending.clear()
        self.step = 0


# ============================================================
# MainWindow
# ============================================================
class MainWindow(QMainWindow):
    sig_log_command = Signal(str)
    sig_log_sensing = Signal(str)

    cur_throttle = 0
    cur_steer = 0

    P95_FLOOR = {
        "idle": 0.010,
        "fwd":  0.020,
        "rev":  0.020,
        "turn": 0.030,
    }
    P95_FALLBACK = {
        "idle": 0.020,
        "fwd":  0.050,
        "rev":  0.050,
        "turn": 0.080,
    }

    THRESH_BY_STATE = {
        "idle": {"warn": 1.10, "intervene": 1.25, "persist": 2},
        "fwd":  {"warn": 1.03, "intervene": 1.10, "persist": 2},
        "rev":  {"warn": 1.03, "intervene": 1.10, "persist": 2},
        "turn": {"warn": 1.06, "intervene": 1.15, "persist": 2},
        "_default": {"warn": 1.05, "intervene": 1.15, "persist": 2},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        try:
            self.ui.commandTable.document().setMaximumBlockCount(120)
            self.ui.sensingTable.document().setMaximumBlockCount(200)
        except Exception:
            pass

        self.sig_log_command.connect(self.update_command_ui)
        self.sig_log_sensing.connect(self.update_sensing_ui)

        self.client = None
        self.mqtt_connected = False

        self.upload_thread = TelemetryUploadThread()

        # predictor init
        self.engine = None
        try:
            self.engine = PredictorEngine()
            self.sig_log_command.emit(f"System: Predictor loaded on {self.engine.device}")
        except Exception as e:
            self.sig_log_command.emit(f"Error: Predictor init failed - {e}")

        self.state_name = "idle"

        # new preset p95 baseline load (supports p95/p90/p50/n/...)
        self.baseline_p95, self.preset_meta = self._load_preset_p95(PRESET_P95_PATH)
        self._apply_p95_safety()

        # baseline summary
        meta_str = []
        for st in ["idle", "fwd", "rev", "turn"]:
            p = self.baseline_p95.get(st, None)
            n = self.preset_meta.get(st, {}).get("n", None)
            if p is None:
                meta_str.append(f"{st}=None")
            else:
                if n is None:
                    meta_str.append(f"{st}={p:.6f}")
                else:
                    meta_str.append(f"{st}={p:.6f}(n={n})")
        wq = self.preset_meta.get("_global", {}).get("winsorize_q", None)
        if wq is not None:
            meta_str.append(f"winsorize_q={wq}")
        self.sig_log_command.emit("System: p95 baseline => " + ", ".join(meta_str))

        # optional: keep hist (debug / optional drift adaptation)
        self.score_hist = defaultdict(lambda: deque(maxlen=800))

        # persistence counters
        self.level = 0
        self._over_counter = 0
        self._over_counter2 = 0

        self.ENABLE_BASELINE_UPDATE = False

        self._warmup_counter = 0
        self._warmup_print_every = 25

        self.last_status = None
        self.last_status_ts = 0.0

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._ui_tick)
        self._ui_timer.start(1000)

        self.sig_log_command.emit("System: Ready")

    # ---------------- preset loader (new json format) ----------------
    def _load_preset_p95(self, path):
        """
        Supports preset files like:
          {
            "idle": {"p95":..., "p90":..., "p50":..., "n":..., "winsorize_q":0.99},
            "fwd":  {"p95":..., ...},
            ...
          }
        Also accepts older:
          {"idle":{"p95":...,"n":...}, ...} or {"idle":0.0123, ...}

        Returns:
          baseline_p95: dict[str,float]
          meta: dict[str,dict]  # per-state extras, plus "_global"
        """
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)

        baseline = {}
        meta = {}

        # try to capture a global winsorize_q if present in any state
        global_wq = None

        for st, v in obj.items():
            if isinstance(v, dict):
                # main value
                baseline[st] = float(v.get("p95", 0.0))
                # meta
                m = {}
                for k in ("n", "p90", "p50", "winsorize_q"):
                    if k in v:
                        m[k] = v[k]
                meta[st] = m
                if global_wq is None and "winsorize_q" in v:
                    global_wq = v["winsorize_q"]
            else:
                baseline[st] = float(v)
                meta[st] = {}

        if global_wq is not None:
            meta["_global"] = {"winsorize_q": global_wq}

        if not baseline:
            raise RuntimeError(f"Failed to load preset p95: empty ({path})")
        return baseline, meta

    def _apply_p95_safety(self):
        """
        1) fill missing state p95 with fallback
        2) clamp with per-state floor
        """
        for st, v in self.P95_FALLBACK.items():
            if st not in self.baseline_p95 or self.baseline_p95[st] is None:
                self.baseline_p95[st] = float(v)

        for st, floor in self.P95_FLOOR.items():
            if st in self.baseline_p95 and self.baseline_p95[st] is not None:
                self.baseline_p95[st] = max(float(self.baseline_p95[st]), float(floor))

    # ---------------- UI updates ----------------
    @Slot(str)
    def update_command_ui(self, msg):
        try:
            self.ui.commandTable.appendPlainText(msg)
            self.ui.commandTable.verticalScrollBar().setValue(
                self.ui.commandTable.verticalScrollBar().maximum()
            )
        except Exception:
            pass

    @Slot(str)
    def update_sensing_ui(self, msg):
        try:
            sb = self.ui.sensingTable.verticalScrollBar()
            at_bottom = (sb.maximum() - sb.value() < 10)
            self.ui.sensingTable.appendPlainText(msg)
            if at_bottom:
                sb.setValue(sb.maximum())
        except Exception:
            pass

    def _ui_tick(self):
        pass

    # ============================================================
    # Control publish
    # ============================================================
    def sendControlCommand(self, label):
        if not self.mqtt_connected:
            self.sig_log_command.emit("Error: MQTT not connected")
            return
        payload = {"throttle": int(self.cur_throttle), "steer": int(self.cur_steer)}
        self.client.publish(TOPIC_PUB_CONTROL, json.dumps(payload), qos=1)
        t = datetime.now(korea_timezone).strftime("%H:%M:%S")
        self.sig_log_command.emit(f"[{t}] {label} >> T:{self.cur_throttle}, S:{self.cur_steer}")

    def start(self):
        try:
            txt = self.ui.startBtn.text()
        except Exception:
            txt = "START"

        if txt == "START":
            try:
                self.ui.startBtn.setText("STOP")
            except Exception:
                pass
            self.mqtt_init()
            if not self.upload_thread.isRunning():
                self.upload_thread.running = True
                self.upload_thread.start()
                self.sig_log_command.emit("System: Firebase Upload Started")
        else:
            try:
                self.ui.startBtn.setText("START")
            except Exception:
                pass
            self.mqtt_disconnect()
            if self.engine:
                self.engine.reset()
            if self.upload_thread.isRunning():
                self.upload_thread.stop()
                self.upload_thread.wait()
                self.sig_log_command.emit("System: Firebase Upload Stopped")

    def go(self):
        self.cur_throttle = 60
        self.sendControlCommand("GO")

    def mid(self):
        self.cur_throttle = 0
        self.cur_steer = 0
        self.sendControlCommand("STOP")

    def back(self):
        self.cur_throttle = -60
        self.sendControlCommand("BACK")

    def left(self):
        self.cur_steer = -100
        self.sendControlCommand("LEFT")

    def right(self):
        self.cur_steer = 100
        self.sendControlCommand("RIGHT")

    def enter(self):
        self.sig_log_command.emit("System: ENTER")

    # ============================================================
    # State gating
    # ============================================================
    def _infer_state_from_cmd(self, thr, steer):
        thr = float(thr)
        steer = float(steer)
        if abs(thr) < 1e-6 and abs(steer) < 1e-6:
            return "idle"
        if abs(steer) >= 50:
            return "turn"
        if thr > 0:
            return "fwd"
        if thr < 0:
            return "rev"
        return "idle"

    # ============================================================
    # Decision
    # ============================================================
    def _get_score_norm(self, state, score):
        p95 = self.baseline_p95.get(state, None)
        if p95 is None or p95 <= 1e-12:
            return None
        return float(score) / float(p95)

    def _get_thresholds_for_state(self, state):
        cfg = self.THRESH_BY_STATE.get(state, None) or self.THRESH_BY_STATE["_default"]
        return float(cfg["warn"]), float(cfg["intervene"]), int(cfg["persist"])

    def _decision_gate(self, state, score_norm):
        if score_norm is None:
            self.level = 0
            self._over_counter = 0
            self._over_counter2 = 0
            return self.level

        warn_th, int_th, persist_n = self._get_thresholds_for_state(state)

        if score_norm > warn_th:
            self._over_counter += 1
        else:
            self._over_counter = 0

        if score_norm > int_th:
            self._over_counter2 += 1
        else:
            self._over_counter2 = 0

        if self._over_counter2 >= persist_n:
            self.level = 2
        elif self._over_counter >= persist_n:
            self.level = 1
        else:
            self.level = 0

        return self.level

    def _maybe_update_baseline(self, state, score, level):
        if not self.ENABLE_BASELINE_UPDATE:
            return
        if level >= 1:
            return

        self.score_hist[state].append(float(score))
        hist = self.score_hist[state]
        if len(hist) >= 60:
            new_p95 = float(np.percentile(np.array(hist, dtype=np.float32), 95))
            floor = self.P95_FLOOR.get(state, 0.0)
            self.baseline_p95[state] = max(new_p95, floor)

    def _apply_soft_intervention(self, level):
        if level < 2:
            return
        pass

    # ============================================================
    # MQTT
    # ============================================================
    def mqtt_init(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.client.connect(BROKER_IP, BROKER_PORT)
        self.client.loop_start()
        self.sig_log_command.emit(f"System: Connecting to {BROKER_IP}:{BROKER_PORT}")

    def mqtt_disconnect(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self.mqtt_connected = False
        self.sig_log_command.emit("System: MQTT Disconnected")

    def on_connect(self, client, userdata, flags, rc, prop):
        if rc == 0:
            self.mqtt_connected = True
            self.sig_log_command.emit("System: MQTT Connected")
            client.subscribe(TOPIC_SUB_TELEMETRY, qos=1)
            client.subscribe(TOPIC_SUB_STATUS, qos=1)

    def on_disconnect(self, client, userdata, flags, rc, prop):
        self.mqtt_connected = False

    def _handle_status_message(self, payload_text):
        self.last_status_ts = time.time()

        try:
            obj = json.loads(payload_text)
            self.last_status = obj

            typ = str(obj.get("type", "")).upper()
            event = str(obj.get("event", ""))
            ts_ms = obj.get("ts_ms", 0)

            if isinstance(ts_ms, (int, float)) and ts_ms > 0:
                t = datetime.fromtimestamp(ts_ms / 1000.0, tz=korea_timezone).strftime("%H:%M:%S")
            else:
                t = datetime.now(korea_timezone).strftime("%H:%M:%S")

            if typ == "ALERT":
                self.sig_log_sensing.emit(f"[{t}] MCU_ALERT: {event}")
            else:
                self.sig_log_sensing.emit(f"[{t}] STATUS: {obj}")
            return
        except Exception:
            pass

        s = payload_text.strip()
        t = datetime.now(korea_timezone).strftime("%H:%M:%S")
        if s.startswith("$STS"):
            self.sig_log_sensing.emit(f"[{t}] MCU_EVENT: {s}")
            self.last_status = {"raw": s}
        else:
            self.sig_log_sensing.emit(f"[{t}] STATUS: {s}")
            self.last_status = {"raw": s}

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload_text = msg.payload.decode(errors="ignore")
        except Exception:
            payload_text = ""

        if topic == TOPIC_SUB_STATUS:
            self._handle_status_message(payload_text)
            return

        if topic != TOPIC_SUB_TELEMETRY:
            return

        try:
            data = json.loads(payload_text)

            if self.upload_thread.isRunning():
                self.upload_thread.update_data(data)

            if not self.engine:
                return

            thr = float(data.get("throttle", 0))
            steer = float(data.get("steer", 0))
            self.state_name = self._infer_state_from_cmd(thr, steer)

            score = self.engine.update(data)

            ts = int(data.get("ts_ms", 0))
            if ts > 0:
                tstamp = datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S.%f")[:-3]
            else:
                tstamp = datetime.now(korea_timezone).strftime("%H:%M:%S")

            if score is None:
                self._warmup_counter += 1
                if self._warmup_counter % self._warmup_print_every == 0:
                    self.sig_log_sensing.emit(
                        f"[{tstamp}] Warmup... xbuf={len(self.engine.x_buf)}/{self.engine.T_IN} "
                        f"pending={len(self.engine.pending)} state={self.state_name}"
                    )
                return

            self._warmup_counter = 0

            score_norm = self._get_score_norm(self.state_name, score)
            level = self._decision_gate(self.state_name, score_norm)

            self._maybe_update_baseline(self.state_name, score, level)
            self._apply_soft_intervention(level)

            p95 = self.baseline_p95.get(self.state_name, None)
            warn_th, int_th, persist_n = self._get_thresholds_for_state(self.state_name)

            if score_norm is None or p95 is None:
                self.sig_log_sensing.emit(
                    f"[{tstamp}] score={score:.6f} state={self.state_name} (no p95)"
                )
            else:
                self.sig_log_sensing.emit(
                    f"[{tstamp}] score={score:.6f} norm={score_norm:.2f} p95={p95:.6f} "
                    f"state={self.state_name} level={level} "
                    f"(warn>{warn_th:.2f}, int>{int_th:.2f}, n={persist_n})"
                )

        except Exception as e:
            self.sig_log_command.emit(f"Rx Error: {e}")

    def closeEvent(self, event):
        self.mqtt_disconnect()
        if self.upload_thread.isRunning():
            self.upload_thread.stop()
            self.upload_thread.wait()
        if self.engine:
            self.engine.reset()
        event.accept()


# ============================================================
# Entry
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

