import json
import time
import math
from datetime import datetime

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Signal, Slot, QTimer

from ui_form import Ui_MainWindow

from config import KOREA_TZ
from mqtt_manager import MqttManager
from predictor_engine import PredictorEngine
from firebase_uploader import init_firestore, TelemetryUploadThread, upload_alert


class MainWindow(QMainWindow):
    sig_log_command = Signal(str)
    sig_log_sensing = Signal(str)

    cur_throttle = 0
    cur_steer = 0

    def __init__(self, broker_ip=None, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # UI log buffer limits
        try:
            self.ui.commandTable.document().setMaximumBlockCount(120)
            self.ui.sensingTable.document().setMaximumBlockCount(200)
        except Exception:
            pass

        self.sig_log_command.connect(self.update_command_ui)
        self.sig_log_sensing.connect(self.update_sensing_ui)

        # --------------------------------------------------
        # Control mode (GUI / Gesture)
        # --------------------------------------------------
        self.control_mode = "GUI"
        self._apply_mode_ui()

        # --------------------------------------------------
        # Firebase
        # --------------------------------------------------
        self.db = init_firestore()
        self.upload_thread = TelemetryUploadThread(self.db)

        # --------------------------------------------------
        # Predictor engine
        # --------------------------------------------------
        self.engine = None
        try:
            self.engine = PredictorEngine()
            self.sig_log_command.emit(
                f"System: Predictor loaded on {self.engine.device}"
            )
        except Exception as e:
            self.sig_log_command.emit(
                f"Error: Predictor init failed - {e}"
            )

        # --------------------------------------------------
        # MQTT manager
        # --------------------------------------------------
        self.mqtt = MqttManager(
            broker_ip=broker_ip,
            on_log=lambda s: self.sig_log_command.emit(s),
            on_connected=self._on_mqtt_connected,
            on_telemetry=self._on_telemetry_text,
            on_status=self._on_status_text,
        )

        # --------------------------------------------------
        # Anomaly score output control (1 Hz)
        # --------------------------------------------------
        self._latest_anomaly_score = None
        self._last_printed_score = None
        self._last_printed_ts = 0.0

        # --------------------------------------------------
        # US_BRAKE debounce and recent window
        # --------------------------------------------------
        self._last_us_brake_ts = 0.0
        self._us_brake_recent_until = 0.0

        # --------------------------------------------------
        # Hold-off / freeze policies
        # --------------------------------------------------
        # (A) Disable baseline update for 1.5s after BRAKE
        self.BASELINE_FREEZE_AFTER_BRAKE_SEC = 1.5
        self._baseline_freeze_until = 0.0

        # (B) Suppress alerts for 1.0s after BRAKE
        self.ALERT_MUTE_AFTER_BRAKE_SEC = 1.0
        self._alert_mute_until = 0.0

        # (C) Disable idle baseline update for 0.7s after idle entry
        self.IDLE_BASELINE_FREEZE_ON_ENTRY_SEC = 0.7
        self._idle_baseline_freeze_until = 0.0

        # Previous state for transition detection
        self._prev_state = None

        # --------------------------------------------------
        # Baseline parameters
        # --------------------------------------------------
        self.BASELINE_BURNIN_N = 60
        self.BASELINE_K = 4.0
        self.BASELINE_SAFE_RATIO = 0.7
        self.BASELINE_EWMA_ALPHA = 0.02

        self._baseline = {}
        self._last_alert_ts = {}

        # Cached telemetry for state classification
        self._last_throttle = 0.0
        self._last_steer = 0.0

        # Baseline status periodic output
        self._baseline_last_ui_ts = 0.0
        self._baseline_last_text = ""
        self.BASELINE_UI_INTERVAL = 2.0

        # --------------------------------------------------
        # UI timer (1 Hz)
        # --------------------------------------------------
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._ui_tick)
        self._ui_timer.start(1000)

        self.sig_log_command.emit("System: Ready")

    # ==================================================
    # Mode UI helper
    # ==================================================
    def _apply_mode_ui(self):
        is_gui = (self.control_mode == "GUI")

        for w in [
            self.ui.goBtn,
            self.ui.brakeBtn,
            self.ui.backBtn,
            self.ui.leftBtn,
            self.ui.rightBtn,
            self.ui.midBtn,
        ]:
            try:
                w.setEnabled(is_gui)
            except Exception:
                pass

        try:
            if is_gui:
                self.ui.modeSwitchBtn.setText("Switch to Gesture Mode")
            else:
                self.ui.modeSwitchBtn.setText("Switch to GUI Mode")
        except Exception:
            pass

    def _publish_current_mode_if_possible(self):
        try:
            self.mqtt.publish_mode(self.control_mode)
        except Exception:
            pass

    # ==================================================
    # UI log slots
    # ==================================================
    @Slot(str)
    def update_command_ui(self, msg: str):
        try:
            self.ui.commandTable.appendPlainText(msg)
            self.ui.commandTable.verticalScrollBar().setValue(
                self.ui.commandTable.verticalScrollBar().maximum()
            )
        except Exception:
            pass

    @Slot(str)
    def update_sensing_ui(self, msg: str):
        try:
            sb = self.ui.sensingTable.verticalScrollBar()
            at_bottom = (sb.maximum() - sb.value() < 10)
            self.ui.sensingTable.appendPlainText(msg)
            if at_bottom:
                sb.setValue(sb.maximum())
        except Exception:
            pass

    # ==================================================
    # Baseline status formatting
    # ==================================================
    def _baseline_status_text(self) -> str:
        states = ["idle", "fwd", "rev", "turn"]
        parts = []
        for st in states:
            b = self._baseline.get(st)
            if not b:
                parts.append(f"{st}:0/{self.BASELINE_BURNIN_N}")
                continue

            n = int(b.get("n", 0))
            if b.get("thr") is None:
                parts.append(f"{st}:{n}/{self.BASELINE_BURNIN_N}")
            else:
                parts.append(f"{st}:READY")
        return "Baseline[" + " | ".join(parts) + "]"

    # ==================================================
    # Periodic UI tick
    # ==================================================
    def _ui_tick(self):
        if self._latest_anomaly_score is not None:
            now = time.time()
            if (now - self._last_printed_ts) >= 0.95:
                score = float(self._latest_anomaly_score)
                tstamp = datetime.now(KOREA_TZ).strftime("%H:%M:%S")

                if (
                    self._last_printed_score is None
                    or abs(score - self._last_printed_score) >= 1e-12
                ):
                    self.sig_log_sensing.emit(
                        f"[{tstamp}] anomaly_score={score:.6f}"
                    )
                    self._last_printed_score = score

                self._last_printed_ts = now

        now2 = time.time()
        if (now2 - self._baseline_last_ui_ts) >= self.BASELINE_UI_INTERVAL:
            txt = self._baseline_status_text()
            if txt != self._baseline_last_text:
                self.sig_log_command.emit(txt)
                self._baseline_last_text = txt
            self._baseline_last_ui_ts = now2

    # ==================================================
    # Scenario classification
    # ==================================================
    def _get_state(self, throttle: float, steer: float) -> str:
        t = float(throttle)
        s = float(steer)

        if abs(t) < 5 and abs(s) < 10:
            return "idle"
        if abs(s) >= 50:
            return "turn"
        if t > 5:
            return "fwd"
        if t < -5:
            return "rev"
        return "idle"

    # ==================================================
    # Baseline burn-in (Welford)
    # ==================================================
    def _baseline_welford_push(self, state: str, x: float):
        b = self._baseline.get(state)
        if b is None:
            b = {"n": 0, "mean": 0.0, "M2": 0.0, "mu": None, "sigma": None, "thr": None}
            self._baseline[state] = b

        b["n"] += 1
        n = b["n"]
        delta = x - b["mean"]
        b["mean"] += delta / n
        delta2 = x - b["mean"]
        b["M2"] += delta * delta2

        if b["n"] == self.BASELINE_BURNIN_N:
            var = b["M2"] / max(1, (b["n"] - 1))
            sigma = math.sqrt(max(var, 1e-12))
            mu = b["mean"]
            b["mu"] = mu
            b["sigma"] = sigma
            b["thr"] = mu + self.BASELINE_K * sigma

            self.sig_log_command.emit(
                f"Baseline READY[{state}] mu={mu:.6f} sigma={sigma:.6f} thr={b['thr']:.6f}"
            )

    # ==================================================
    # Baseline EWMA update (safe zone only)
    # ==================================================
    def _baseline_ewma_update_if_safe(self, state: str, score: float):
        b = self._baseline.get(state)
        if not b or b["thr"] is None:
            return

        thr = float(b["thr"])
        if thr <= 0:
            return

        if score >= thr * self.BASELINE_SAFE_RATIO:
            return

        alpha = self.BASELINE_EWMA_ALPHA
        mu = float(b["mu"])
        sigma = float(b["sigma"])

        mu_new = (1 - alpha) * mu + alpha * score
        var = sigma * sigma
        var_new = (1 - alpha) * var + alpha * ((score - mu_new) ** 2)
        sigma_new = math.sqrt(max(var_new, 1e-12))

        b["mu"] = mu_new
        b["sigma"] = sigma_new
        b["thr"] = mu_new + self.BASELINE_K * sigma_new

    # ==================================================
    # Alert emission (debounced)
    # ==================================================
    def _emit_alert(self, state: str, score: float, thr: float, telemetry=None):
        now = time.time()
        last = self._last_alert_ts.get(state, 0.0)
        if (now - last) < 1.0:
            return

        tstamp = datetime.now(KOREA_TZ).strftime("%H:%M:%S")
        self.sig_log_sensing.emit(
            f"[{tstamp}] ANOMALY state={state} score={score:.6f} thr={thr:.6f}"
        )

        try:
            alert_doc = {
                "type": "ANOMALY",
                "state": state,
                "score": float(score),
                "threshold": float(thr),
                "telemetry": dict(telemetry) if telemetry else None,
            }
            upload_alert(self.db, alert_doc)
        except Exception:
            pass

        self._last_alert_ts[state] = now

    # ==================================================
    # Control commands
    # ==================================================
    def sendControlCommand(self, label: str):
        self.mqtt.publish_control(self.cur_throttle, self.cur_steer)
        t = datetime.now(KOREA_TZ).strftime("%H:%M:%S")
        self.sig_log_command.emit(
            f"[{t}] {label} >> T:{self.cur_throttle}, S:{self.cur_steer}"
        )

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

            self.mqtt.start()

            if not self.upload_thread.isRunning():
                self.upload_thread.running = True
                self.upload_thread.start()
                self.sig_log_command.emit("System: Firebase Upload Started")
        else:
            try:
                self.ui.startBtn.setText("START")
            except Exception:
                pass

            self.mqtt.stop()

            if self.engine:
                self.engine.reset()

            self._latest_anomaly_score = None
            self._last_printed_score = None
            self._last_printed_ts = 0.0

            self._baseline.clear()
            self._last_alert_ts.clear()
            self._us_brake_recent_until = 0.0

            self._baseline_freeze_until = 0.0
            self._alert_mute_until = 0.0
            self._idle_baseline_freeze_until = 0.0
            self._prev_state = None

            self._baseline_last_ui_ts = 0.0
            self._baseline_last_text = ""

            if self.upload_thread.isRunning():
                self.upload_thread.stop()
                self.upload_thread.wait()
                self.sig_log_command.emit("System: Firebase Upload Stopped")

    def go(self):
        self.cur_throttle = 60
        self.sendControlCommand("GO")

    def mid(self):
        self.cur_steer = 0
        self.sendControlCommand("MID(steer=0)")

    def back(self):
        self.cur_throttle = -60
        self.sendControlCommand("BACK")

    def left(self):
        self.cur_steer = -100
        self.sendControlCommand("LEFT")

    def right(self):
        self.cur_steer = 100
        self.sendControlCommand("RIGHT")

    def brake(self):
        self.cur_throttle = 0
        self.sendControlCommand("BRAKE(throttle=0)")

        now = time.time()
        self._baseline_freeze_until = max(
            self._baseline_freeze_until,
            now + self.BASELINE_FREEZE_AFTER_BRAKE_SEC
        )
        self._alert_mute_until = max(
            self._alert_mute_until,
            now + self.ALERT_MUTE_AFTER_BRAKE_SEC
        )

        self.sig_log_command.emit(
            f"System: BRAKE holdoff baseline={self.BASELINE_FREEZE_AFTER_BRAKE_SEC:.1f}s, "
            f"alert={self.ALERT_MUTE_AFTER_BRAKE_SEC:.1f}s"
        )

    def toggle_mode(self):
        self.control_mode = "Gesture" if self.control_mode == "GUI" else "GUI"
        self._apply_mode_ui()
        self._publish_current_mode_if_possible()
        self.sig_log_command.emit(f"System: Mode switched => {self.control_mode}")

    # ==================================================
    # MQTT callbacks
    # ==================================================
    def _on_mqtt_connected(self):
        self._publish_current_mode_if_possible()

    def _on_status_text(self, payload_text: str):
        """
        Handle US_BRAKE events and apply baseline hold-off.
        Also uploads US_BRAKE to Firestore alert collection.
        """
        text = payload_text.strip()
        status_blob = text
        try:
            obj = json.loads(text)
            status_blob = f"{obj.get('event', '')} {text}"
        except Exception:
            pass

        if "US_BRAKE" in status_blob:
            now = time.time()

            # debounce for UI/logging and Firestore upload
            if now - self._last_us_brake_ts > 0.2:
                tstamp = datetime.now(KOREA_TZ).strftime("%H:%M:%S")
                self.sig_log_sensing.emit(f"[{tstamp}] US_BRAKE")
                self._last_us_brake_ts = now

                # ✅ Upload US_BRAKE to Firestore alert collection
                try:
                    alert_doc = {
                        "type": "US_BRAKE",
                        "source": "MCU",
                        "raw": status_blob,
                    }
                    upload_alert(self.db, alert_doc)
                except Exception:
                    pass

            self._us_brake_recent_until = now + 2.0

    def _on_telemetry_text(self, payload_text: str):
        try:
            data = json.loads(payload_text)

            self._last_throttle = float(data.get("throttle", 0.0))
            self._last_steer = float(data.get("steer", 0.0))

            if self.upload_thread.isRunning():
                self.upload_thread.update_data(data)

            if not self.engine:
                return

            score = self.engine.update(data)
            if score is None:
                return

            score = float(score)
            self._latest_anomaly_score = score

            state = self._get_state(self._last_throttle, self._last_steer)
            now = time.time()

            if self._prev_state != "idle" and state == "idle":
                self._idle_baseline_freeze_until = max(
                    self._idle_baseline_freeze_until,
                    now + self.IDLE_BASELINE_FREEZE_ON_ENTRY_SEC
                )
            self._prev_state = state

            b = self._baseline.get(state)

            alert_allowed = (now >= self._alert_mute_until)
            if b and b.get("thr") is not None:
                thr = float(b["thr"])
                if score > thr and alert_allowed:
                    self._emit_alert(state, score, thr, data)

            if now < self._us_brake_recent_until:
                return
            if now < self._baseline_freeze_until:
                return
            if state == "idle" and now < self._idle_baseline_freeze_until:
                return

            if (b is None) or (b.get("thr") is None):
                self._baseline_welford_push(state, score)
                return

            if score <= float(b["thr"]):
                self._baseline_ewma_update_if_safe(state, score)

        except Exception as e:
            self.sig_log_command.emit(f"Rx Error: {e}")

    # ==================================================
    # Close event
    # ==================================================
    def closeEvent(self, event):
        self.mqtt.stop()

        if self.upload_thread.isRunning():
            self.upload_thread.stop()
            self.upload_thread.wait()

        if self.engine:
            self.engine.reset()

        event.accept()
