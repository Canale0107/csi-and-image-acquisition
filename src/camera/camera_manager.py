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

        index = self.config.camera_index
        logger.info("Opening camera with index %s.", index)
        self.cap = cv2.VideoCapture(index)

        # 解像度を指定
        width = self.config.width
        height = self.config.height
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        resolution = f'{width}x{height}'
        logger.info("Setting camera %d resolution to %s.", index, resolution)

        # FPSを指定
        fps = self.config.fps
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        logger.info("Setting camera %d FPS to %s.", index, fps)

        if not self.cap.isOpened():
            logger.error("Failed to open camera %s.", index)
            raise ValueError("Camera %d cannot be opened.", index)

        logger.info("Camera %s successfully opened.", index)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.cap is not None:
            logger.info("Releasing camera %d.", self.config.camera_index)
            self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Camera and OpenCV resources cleaned up.")
