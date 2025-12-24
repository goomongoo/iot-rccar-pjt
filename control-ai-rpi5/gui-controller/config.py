# config.py
import pytz

# ============================================================
# MQTT
# ============================================================
BROKER_IP = None
BROKER_PORT = 1883

TOPIC_PUB_CONTROL   = "mobility/control/drive"
TOPIC_PUB_MODE      = "mobility/control/mode"
TOPIC_SUB_TELEMETRY = "mobility/telemetry/parsed"
TOPIC_SUB_STATUS    = "mobility/alert/event"

# ============================================================
# Predictor
# ============================================================
MODEL_TS_PATH = "./predictor_ts.pt"
SCALER_PATH   = "./sensor_scaler.pkl"

T_IN = 20
T_OUT = 20
INFER_STRIDE = 5

# cmd scaling (dataset convention)
THR_MIN, THR_MAX = -100.0, 100.0
STR_MIN, STR_MAX = -100.0, 100.0

# ============================================================
# Timezone
# ============================================================
KOREA_TZ = pytz.timezone("Asia/Seoul")

# ============================================================
# Firebase
# ============================================================
FIREBASE_KEY_PATH = "./qt-gui-controller-db-key.json"
FIRESTORE_COLLECTION = "telemetry"
FIRESTORE_ALERT_COLLECTION = "alert"
