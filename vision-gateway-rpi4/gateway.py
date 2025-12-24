#!/usr/bin/env python3
"""
gateway.py

MQTT <-> UART bridge with mode switching.

Subscriptions:
- mobility/control/mode
    - "GUI"     -> send UART commands from mobility/control/drive
    - "Gesture" -> send UART commands from camera gesture recognition
- mobility/control/drive (used only in GUI mode)

Publications:
- Telemetry:
    - UART "$TEL,..." -> mobility/telemetry/parsed
- Alerts (optional):
    - UART "$STS,..." -> mobility/alert/event
"""

import sys
import time
import json
import threading
import os
import argparse

import serial
import paho.mqtt.client as mqtt

# ---------------- Optional gesture dependencies ----------------
try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    GESTURE_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Gesture dependencies not available: {e}")
    GESTURE_AVAILABLE = False

# ---------------- Configuration ----------------
BROKER_PORT = 1883

TOPIC_DRIVE = "mobility/control/drive"
TOPIC_MODE = "mobility/control/mode"

TOPIC_TEL = "mobility/telemetry/parsed"
TOPIC_ALERT = "mobility/alert/event"

DEFAULT_SERIAL_CANDIDATES = [
    "/dev/serial0",
    "/dev/ttyAMA0",
    "/dev/ttyS0",
    "/dev/serial1",
]

BAUD_RATE = 115200

MODE_GUI = "GUI"
MODE_GESTURE = "Gesture"

# ---------------- Shared state ----------------
ser = None
uart_lock = threading.Lock()

current_mode = MODE_GUI
mode_lock = threading.Lock()

client = None

# Runtime options (from argparse)
BROKER_ADDRESS = None
SERIAL_PORT = None

# ---------------- Helpers ----------------
def set_mode(new_mode: str) -> None:
    """Set the current mode safely. Only GUI or Gesture is allowed."""
    global current_mode
    with mode_lock:
        if new_mode not in (MODE_GUI, MODE_GESTURE):
            print(f"[MODE] Ignored unknown mode: {new_mode}")
            return
        if current_mode != new_mode:
            current_mode = new_mode
            print(f"[MODE] Switched -> {current_mode}")


def get_mode() -> str:
    """Get the current mode safely."""
    with mode_lock:
        return current_mode


def make_control_packet(throttle: int, steer: int) -> str:
    """Build a UART control packet."""
    return f"$CMD,{int(throttle)},{int(steer)}\n"


def uart_send_cmd(throttle: int, steer: int, src: str = "") -> None:
    """Send a UART command using a global lock to avoid concurrent writes."""
    packet = make_control_packet(throttle, steer)
    with uart_lock:
        if ser and ser.is_open:
            ser.write(packet.encode("utf-8"))
            tag = f"[{src}]" if src else ""
            print(f"[CMD TX]{tag} {packet.strip()}")


def parse_telemetry(line: str) -> str | None:
    """
    Parse a "$TEL" UART line into a JSON string.

    Expected format:
      $TEL,ax,ay,az,gx,gy,gz,dist_cm,throttle,steer
    """
    try:
        parts = line.split(",")
        if len(parts) != 10:
            return None

        payload = {
            "ts_ms": int(time.time() * 1000),
            "ax": int(parts[1]),
            "ay": int(parts[2]),
            "az": int(parts[3]),
            "gx": int(parts[4]),
            "gy": int(parts[5]),
            "gz": int(parts[6]),
            "dist_cm": int(parts[7]),
            "throttle": int(parts[8]),
            "steer": int(parts[9].strip()),
        }
        return json.dumps(payload)
    except Exception as e:
        print(f"[TEL Parse Error] {e} | line={line}")
        return None


def parse_mode_payload(payload_bytes: bytes) -> str:
    """
    Accept either:
      1) Plain text: "GUI" or "Gesture"
      2) JSON: {"mode":"GUI"} or {"mode":"Gesture"}
    """
    s = payload_bytes.decode("utf-8", errors="ignore").strip()
    if not s:
        return ""
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            return str(obj.get("mode", "")).strip()
        except Exception:
            return ""
    return s


def _resolve_realpath(path: str) -> str:
    """Return real path for device (symlink target)."""
    try:
        return os.path.realpath(path)
    except Exception:
        return path


def _try_open_serial(port: str, baud: int, timeout: float = 0.1) -> serial.Serial | None:
    """Try opening the given serial port; return Serial on success else None."""
    try:
        s = serial.Serial(port, baud, timeout=timeout)
        s.flush()
        return s
    except Exception:
        return None


def pick_serial_port(user_port: str | None, candidates: list[str]) -> tuple[str, serial.Serial]:
    """
    Pick a working serial port.
    - If user_port is provided, try it first (and fail hard if not working).
    - Else, probe candidates in order, return first that opens.
    """
    if user_port:
        s = _try_open_serial(user_port, BAUD_RATE, timeout=0.1)
        if not s:
            raise RuntimeError(f"Failed to open requested serial port: {user_port}")
        return user_port, s

    tried = []
    for p in candidates:
        if not p:
            continue
        if not os.path.exists(p):
            tried.append(f"{p} (missing)")
            continue
        s = _try_open_serial(p, BAUD_RATE, timeout=0.1)
        if s:
            return p, s
        tried.append(f"{p} (open failed)")

    raise RuntimeError("No usable serial port found. Tried: " + ", ".join(tried))


# ---------------- MQTT callbacks ----------------
def on_connect(mqtt_client, userdata, flags, reason_code, properties):
    """Subscribe to required topics after successful connection."""
    if reason_code == 0:
        print("[MQTT] Connected.")
        print(f"[MQTT] Subscribing: {TOPIC_MODE}, {TOPIC_DRIVE}")
        mqtt_client.subscribe(TOPIC_MODE)
        mqtt_client.subscribe(TOPIC_DRIVE)
    else:
        print(f"[MQTT] Connection failed: {reason_code}")


def on_message(mqtt_client, userdata, msg):
    """Handle incoming MQTT messages."""
    try:
        if msg.topic == TOPIC_MODE:
            new_mode = parse_mode_payload(msg.payload)
            if new_mode:
                set_mode(new_mode)
            return

        if msg.topic == TOPIC_DRIVE:
            # Drive commands are applied only in GUI mode
            if get_mode() != MODE_GUI:
                return

            payload_str = msg.payload.decode("utf-8", errors="ignore")
            data = json.loads(payload_str)
            throttle = int(data.get("throttle", 0))
            steer = int(data.get("steer", 0))
            uart_send_cmd(throttle, steer, src="GUI")
            return

    except Exception as e:
        print(f"[MQTT RX Error] {e}")


# ---------------- Gesture mapping ----------------
# Values can be tuned for the specific vehicle.
GESTURE_MAP: dict[str, tuple[int, int]] = {
    "Thumb_Up":    (60, 0),
    "Thumb_Down":  (-60, 0),
    "Closed_Fist": (0, 0),
    "Open_Palm":   (0, 0),
    "Pointing_Up": (0, -100),
    "Victory":     (0, 100),
}


class GestureWorker(threading.Thread):
    """
    Gesture recognition worker thread.

    - Keeps the camera open continuously
    - Runs inference only in Gesture mode
    - Drops frames when busy to maintain low latency
    - Uses only the latest recognition result
    """

    def __init__(
        self,
        model_path: str = "gesture_recognizer.task",
        camera_id: int = 0,
        width: int = 320,
        height: int = 240,
        min_interval_sec: float = 0.12,
    ):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.min_interval_sec = min_interval_sec

        self._stop_evt = threading.Event()
        self._recognizer = None
        self._cap = None

        self._last_sent_ts = 0.0
        self._last_gesture = None

        self._proc_lock = threading.Lock()
        self._is_processing = False
        self._latest_result = None
        self._latest_result_ts_ms = 0

    def stop(self) -> None:
        """Signal the worker thread to stop."""
        self._stop_evt.set()

    def _send_by_gesture(self, category_name: str) -> None:
        """Send a UART command based on the recognized gesture."""
        if get_mode() != MODE_GESTURE:
            return
        if category_name not in GESTURE_MAP:
            return

        now = time.time()
        if (now - self._last_sent_ts) < self.min_interval_sec:
            return

        if self._last_gesture == category_name:
            return

        throttle, steer = GESTURE_MAP[category_name]
        uart_send_cmd(throttle, steer, src=f"GEST:{category_name}")
        self._last_sent_ts = now
        self._last_gesture = category_name

    def _on_result(
        self,
        result: vision.GestureRecognizerResult,
        unused_output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        """Async callback for MediaPipe gesture recognition results."""
        with self._proc_lock:
            self._latest_result = result
            self._latest_result_ts_ms = timestamp_ms
            self._is_processing = False

    def _init_mediapipe(self) -> None:
        """Initialize MediaPipe GestureRecognizer in LIVE_STREAM mode."""
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=self._on_result,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def _init_camera(self) -> None:
        """Open the camera and apply resolution settings."""
        self._cap = cv2.VideoCapture(self.camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def run(self) -> None:
        """Main worker loop."""
        if not GESTURE_AVAILABLE:
            print("[GestureWorker] Disabled (dependencies missing).")
            return

        try:
            self._init_camera()
            self._init_mediapipe()
            print("[GestureWorker] Started.")
        except Exception as e:
            print(f"[GestureWorker] Init failed: {e}")
            return

        try:
            while not self._stop_evt.is_set() and self._cap and self._cap.isOpened():
                ok, frame = self._cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                if get_mode() != MODE_GESTURE:
                    self._last_gesture = None
                    with self._proc_lock:
                        self._latest_result = None
                        self._latest_result_ts_ms = 0
                    time.sleep(0.03)
                    continue

                with self._proc_lock:
                    busy = self._is_processing

                if not busy:
                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb,
                    )

                    with self._proc_lock:
                        self._is_processing = True

                    ts_ms = time.time_ns() // 1_000_000
                    self._recognizer.recognize_async(mp_image, ts_ms)
                else:
                    time.sleep(0.001)

                result_to_use = None
                with self._proc_lock:
                    if self._latest_result is not None:
                        result_to_use = self._latest_result
                        self._latest_result = None

                if result_to_use and result_to_use.gestures:
                    gesture = result_to_use.gestures[0][0]
                    name = gesture.category_name
                    if name and name != "None":
                        self._send_by_gesture(name)

                time.sleep(0.001)

        except Exception as e:
            print(f"[GestureWorker] Runtime error: {e}")

        finally:
            try:
                if self._recognizer:
                    self._recognizer.close()
            except Exception:
                pass
            try:
                if self._cap:
                    self._cap.release()
            except Exception:
                pass
            print("[GestureWorker] Stopped and resources released.")


# ---------------- Initialization and main loop ----------------
def init_serial() -> None:
    """Open the UART port (auto-detect across RPi4/RPi5)."""
    global ser, SERIAL_PORT

    try:
        chosen_port, opened = pick_serial_port(SERIAL_PORT, DEFAULT_SERIAL_CANDIDATES)
        ser = opened
        real = _resolve_realpath(chosen_port)
        if chosen_port != real:
            print(f"[UART] Opened: {chosen_port} -> {real} @ {BAUD_RATE}")
        else:
            print(f"[UART] Opened: {chosen_port} @ {BAUD_RATE}")
    except Exception as e:
        print(f"[UART] Open failed: {e}")
        print("[HINT] If you know the exact device, run with: --serial /dev/ttyAMA0 (or /dev/serial0)")
        sys.exit(1)


def init_mqtt() -> mqtt.Client:
    """Connect to MQTT broker and start the network loop."""
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_client.connect(BROKER_ADDRESS, BROKER_PORT)
        mqtt_client.loop_start()
        return mqtt_client
    except Exception as e:
        print(f"[MQTT] Connect failed: {e}")
        sys.exit(1)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MQTT <-> UART gateway bridge")
    p.add_argument(
        "--broker",
        required=True,
        help="MQTT broker IPv4/hostname (required). Example: --broker 192.168.0.75",
    )
    p.add_argument(
        "--port",
        type=int,
        default=BROKER_PORT,
        help=f"MQTT broker port (default: {BROKER_PORT})",
    )
    p.add_argument(
        "--serial",
        default=None,
        help="Serial device path (optional). If omitted, auto-detect among /dev/serial0,/dev/ttyAMA0,/dev/ttyS0,...",
    )
    return p.parse_args(argv)


def main() -> None:
    global client, BROKER_ADDRESS, BROKER_PORT, SERIAL_PORT

    args = parse_args(sys.argv[1:])
    BROKER_ADDRESS = args.broker
    BROKER_PORT = int(args.port)
    SERIAL_PORT = args.serial

    init_serial()
    client = init_mqtt()

    gesture_worker = GestureWorker(
        model_path="gesture_recognizer.task",
        camera_id=0,
        width=320,
        height=240,
        min_interval_sec=0.12,
    )
    gesture_worker.start()

    print("=== UART <-> MQTT Bridge Running ===")
    print(f"[MQTT] Broker: {BROKER_ADDRESS}:{BROKER_PORT}")
    print(f"[MODE] Default: {MODE_GUI} (publish to {TOPIC_MODE} to switch)")

    try:
        while True:
            if ser.in_waiting > 0:
                try:
                    with uart_lock:
                        line = ser.readline().decode(
                            "utf-8",
                            errors="ignore",
                        ).strip()

                    if not line:
                        time.sleep(0.001)
                        continue

                    if line.startswith("$TEL"):
                        json_payload = parse_telemetry(line)
                        if json_payload:
                            client.publish(TOPIC_TEL, json_payload)

                    elif line.startswith("$STS"):
                        print(f"[STS RX] {line}")
                        parts = line.split(",")
                        if len(parts) >= 2:
                            event_type = parts[1].strip()
                            alert_payload = {
                                "type": "ALERT",
                                "event": event_type,
                                "ts_ms": int(time.time() * 1000),
                            }
                            client.publish(
                                TOPIC_ALERT,
                                json.dumps(alert_payload),
                            )
                            print(f"[ALERT Pub] {alert_payload}")

                    else:
                        pass

                except Exception as e:
                    print(f"[UART] Read error: {e}")

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\n[SYS] Stopping...")

    finally:
        try:
            gesture_worker.stop()
        except Exception:
            pass

        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

        try:
            if ser:
                ser.close()
        except Exception:
            pass

        print("[SYS] Clean shutdown complete.")


if __name__ == "__main__":
    main()
