import json
import paho.mqtt.client as mqtt

from config import (
    BROKER_PORT,
    TOPIC_PUB_CONTROL,
    TOPIC_PUB_MODE,
    TOPIC_SUB_TELEMETRY,
    TOPIC_SUB_STATUS,
)


class MqttManager:
    """
    MQTT wrapper independent from Qt.
    """

    def __init__(
        self,
        broker_ip: str,
        on_log,
        on_connected,
        on_telemetry,
        on_status,
        on_disconnected=None,
    ):
        if not broker_ip:
            raise ValueError("broker_ip must be provided")

        self.broker_ip = broker_ip
        self.broker_port = int(BROKER_PORT)

        self.on_log = on_log
        self.on_connected = on_connected
        self.on_telemetry = on_telemetry
        self.on_status = on_status
        self.on_disconnected = on_disconnected

        self.client = None
        self.connected = False

    def start(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.client.connect(self.broker_ip, self.broker_port)
        self.client.loop_start()

        self.on_log(
            f"System: Connecting to {self.broker_ip}:{self.broker_port}"
        )

    def stop(self):
        if not self.client:
            return

        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

        self.connected = False
        self.on_log("System: MQTT Disconnected")

    def publish_control(self, throttle: int, steer: int):
        if not self.connected or not self.client:
            self.on_log("Error: MQTT not connected")
            return

        payload = {
            "throttle": int(throttle),
            "steer": int(steer),
        }
        self.client.publish(
            TOPIC_PUB_CONTROL,
            json.dumps(payload),
            qos=1,
        )

    def publish_mode(self, mode: str):
        if not self.connected or not self.client:
            self.on_log("Error: MQTT not connected (mode)")
            return

        self.client.publish(TOPIC_PUB_MODE, mode, qos=1)
        self.on_log(f"System: Mode published => {mode}")

    # --------------------------------------------------
    # MQTT callbacks
    # --------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc, prop):
        if rc == 0:
            self.connected = True
            self.on_log("System: MQTT Connected")

            client.subscribe(TOPIC_SUB_TELEMETRY, qos=1)
            client.subscribe(TOPIC_SUB_STATUS, qos=1)

            self.on_connected()

    def _on_disconnect(self, client, userdata, flags, rc, prop):
        self.connected = False
        if self.on_disconnected:
            self.on_disconnected()

    def _on_message(self, client, userdata, msg):
        try:
            payload_text = msg.payload.decode(errors="ignore")
        except Exception:
            payload_text = ""

        if msg.topic == TOPIC_SUB_STATUS:
            self.on_status(payload_text)
        elif msg.topic == TOPIC_SUB_TELEMETRY:
            self.on_telemetry(payload_text)
