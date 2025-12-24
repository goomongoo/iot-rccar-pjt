from collections import deque

import numpy as np
import joblib
import torch

from config import (
    MODEL_TS_PATH,
    SCALER_PATH,
    T_IN,
    T_OUT,
    INFER_STRIDE,
    THR_MIN,
    THR_MAX,
    STR_MIN,
    STR_MAX,
)


class PredictorEngine:
    def __init__(
        self,
        model_path=MODEL_TS_PATH,
        scaler_path=SCALER_PATH,
        t_in=T_IN,
        t_out=T_OUT,
        stride=INFER_STRIDE,
        device=None,
    ):
        self.T_IN = int(t_in)
        self.T_OUT = int(t_out)
        self.stride = int(stride)

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Load TorchScript model
        self.model = torch.jit.load(model_path, map_location=self.device)
        self.model.eval()

        # Load scaler (trained on sensor channels only)
        scaler = joblib.load(scaler_path)
        self.sensor_mean = scaler.mean_[:6].astype(np.float32)
        self.sensor_std = scaler.scale_[:6].astype(np.float32)

        # Input buffer: scaled [6 sensors + 2 commands]
        self.x_buf = deque(maxlen=self.T_IN)

        # Pending prediction queue
        # Each item waits until T_OUT actual frames are collected
        self.pending = deque()

        self.step = 0

        # Output shape validation
        with torch.no_grad():
            y = self.model(torch.zeros(1, self.T_IN, 8))
        if list(y.shape) != [1, self.T_OUT, 6]:
            raise RuntimeError(
                f"Predictor output shape mismatch: got {list(y.shape)}"
            )

    @staticmethod
    def _scale_cmd(v, lo, hi):
        """
        Linearly scale a command value to [-1, 1].
        """
        return 2.0 * (v - lo) / (hi - lo) - 1.0

    def _scale_frame(self, data: dict):
        """
        Scale one telemetry frame.
        Returns:
            x   : scaled input vector [8]
            sensor_s : scaled sensor vector [6]
        """
        sensor = np.array(
            [
                data["ax"],
                data["ay"],
                data["az"],
                data["gx"],
                data["gy"],
                data["gz"],
            ],
            dtype=np.float32,
        )

        sensor_s = (sensor - self.sensor_mean) / (self.sensor_std + 1e-6)

        thr_s = self._scale_cmd(
            float(data["throttle"]),
            THR_MIN,
            THR_MAX,
        )
        str_s = self._scale_cmd(
            float(data["steer"]),
            STR_MIN,
            STR_MAX,
        )

        x = np.array([*sensor_s, thr_s, str_s], dtype=np.float32)
        return x, sensor_s

    @torch.no_grad()
    def _predict(self, x_seq: np.ndarray) -> np.ndarray:
        """
        Run model inference.
        Input shape : [T_IN, 8]
        Output shape: [T_OUT, 6]
        """
        x = torch.from_numpy(x_seq[None]).to(self.device)
        y = self.model(x)
        return y.squeeze(0).cpu().numpy()

    def update(self, data: dict):
        """
        Process one telemetry frame.

        Returns:
            anomaly_score (float) when future T_OUT frames are fully observed.
            None if prediction is not yet complete.
        """
        x_s, sensor_s = self._scale_frame(data)

        # Complete pending prediction by collecting actual future frames
        if self.pending:
            self.pending[0]["actual"].append(sensor_s)
            if len(self.pending[0]["actual"]) == self.T_OUT:
                pred = self.pending[0]["pred"]
                act = np.stack(self.pending[0]["actual"])
                score = float(np.mean((pred - act) ** 2))
                self.pending.popleft()
                return score

        # Push scaled input frame
        self.x_buf.append(x_s)
        self.step += 1

        # Schedule new prediction every stride
        if len(self.x_buf) == self.T_IN and (self.step % self.stride == 0):
            y_pred = self._predict(np.stack(self.x_buf))
            self.pending.append(
                {
                    "pred": y_pred,
                    "actual": [],
                }
            )

        return None

    def reset(self):
        """
        Reset internal buffers and counters.
        """
        self.x_buf.clear()
        self.pending.clear()
        self.step = 0
