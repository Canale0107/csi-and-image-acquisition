import cv2
import logging

from src.config import CameraConfig


logger = logging.getLogger(__name__)


class CameraManager():
    """
    カメラの管理を行う
    """
    def __init__(self, config: CameraConfig) -> None:
        self.cap = None
        self.config = config

    def __enter__(self) -> 'CameraManager':

        logger.info("Opening camera with index %s.", self.config.camera_index)
        self.cap = cv2.VideoCapture(self.config.camera_index)

        # 解像度を指定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)

        logger.info("Setting camera resolution to %s.", f'{self.config.width}x{self.config.height}')

        # FPSを指定
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        logger.info("Setting camera FPS to %s.", self.config.fps)

        if not self.cap.isOpened():
            logger.error("Failed to open camera %s.", self.config.camera_index)
            raise ValueError("Camera %d cannot be opened.", self.config.camera_index)

        logger.info("Camera %s successfully opened.", self.config.camera_index)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.cap is not None:
            logger.info("Releasing camera %d.", self.config.camera_index)
            self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Camera and OpenCV resources cleaned up.")
