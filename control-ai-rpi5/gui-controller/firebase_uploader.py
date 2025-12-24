import time
from datetime import datetime

from PySide6.QtCore import QThread

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_KEY_PATH, FIRESTORE_COLLECTION, FIRESTORE_ALERT_COLLECTION, KOREA_TZ


def init_firestore():
    """
    Initialize Firestore.
    Returns a Firestore client on success, or None on failure.
    The application continues running even if initialization fails.
    """
    try:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized")
        return db
    except Exception as e:
        print("Firebase init failed:", e)
        return None


def upload_alert(db, alert_payload: dict):
    """
    Upload a single alert document to Firestore.

    - Collection: FIRESTORE_ALERT_COLLECTION (default: "alert")
    - Document id: server_time (Asia/Seoul) with milliseconds to reduce collision
    """
    if not db:
        return False

    try:
        ts = datetime.now(KOREA_TZ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        payload = dict(alert_payload or {})
        payload["server_time"] = ts
        db.collection(FIRESTORE_ALERT_COLLECTION).document(ts).set(payload)
        return True
    except Exception as e:
        print("Firebase alert upload error:", e)
        return False


class TelemetryUploadThread(QThread):
    """
    Periodically uploads the latest telemetry data to Firestore.
    Upload interval is 1 second.
    """
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.running = True
        self.latest_data = None

    def update_data(self, data: dict):
        """
        Update the latest telemetry data to be uploaded.
        """
        self.latest_data = data

    def run(self):
        """
        Main thread loop.
        Uploads the latest telemetry data to Firestore every second.
        """
        while self.running:
            time.sleep(1.0)

            if not self.db or not self.latest_data:
                continue

            try:
                ts = datetime.now(KOREA_TZ).strftime("%Y-%m-%d %H:%M:%S")
                payload = dict(self.latest_data)
                payload["server_time"] = ts

                self.db.collection(FIRESTORE_COLLECTION).document(ts).set(payload)
            except Exception as e:
                print("Firebase upload error:", e)

    def stop(self):
        """
        Stop the upload thread loop.
        """
        self.running = False
