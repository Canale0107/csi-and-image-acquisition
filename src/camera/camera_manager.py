import cv2
from src.config import CameraConfig


class CameraManager():
    """
    カメラの管理を行う
    """
    def __init__(self, config: CameraConfig) -> None:
        self.cap = None
        self.config = config

    def __enter__(self) -> 'CameraManager':

        self.cap = cv2.VideoCapture(self.config.camera_index)

        # 解像度を指定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)

        # FPSを指定
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not self.cap.isOpened():
            raise ValueError(f"Camera {self.config.camera_index} cannot be opened.")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()