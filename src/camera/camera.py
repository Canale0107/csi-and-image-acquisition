import logging

import numpy as np
import cv2

from src.config import CameraConfig

logger = logging.getLogger(__name__)


# TODO: 抽象的なDataWriterクラスを作って継承させる
class Camera:
    def __init__(self, cap) -> None:
        self.cap = cap

    def read_frame(self) -> np.ndarray:
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to capture frame from camera.")
        frame = cv2.flip(frame, 1)  # 画像の左右反転
        return frame


# CameraとはすなわちCamera
class CameraManager:
    """
    カメラの管理を行う
    """
    def __init__(self, config: CameraConfig) -> None:
        self.cap = None
        self.index = config.camera_index
        self.width = config.width
        self.height = config.height
        self.fps = config.fps

    def __enter__(self) -> 'CameraManager':

        logger.info("Opening camera with index %s.", self.index)
        self.cap = cv2.VideoCapture(self.index)

        # 解像度を指定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        resolution = f'{self.width}x{self.height}'
        logger.info("Setting camera %d resolution to %s.", self.index, resolution)

        # FPSを指定
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        logger.info("Setting camera %d FPS to %s.", self.index, self.fps)

        if not self.cap.isOpened():
            logger.error("Failed to open camera %d.", self.index)
            raise ValueError(f"Camera {self.index} cannot be opened.")

        logger.info("Camera %s successfully opened.", self.index)
        return self

    def get_reader(self) -> Camera:
        if self.cap is None:
            raise RuntimeError("Recording not started.")
        return Camera(self.cap)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.cap is not None:
            logger.info("Releasing camera %d.", self.index)
            self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Camera %d and OpenCV resources cleaned up.", self.index)
