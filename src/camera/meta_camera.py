import os
from datetime import datetime, timezone
from pathlib import Path
import logging

import numpy as np
import cv2
from pydantic import BaseModel

from src.config import CameraConfig, DataAcquisitionConfig
from src.camera.camera import  Camera, CameraManager
from src.utils import FilePathManager


logger = logging.getLogger(__name__)


class MetaData(BaseModel):
    session_id: str
    camera_index: int
    timestamp: datetime
    filepath: Path


class MetaFrame:
    def __init__(self, frame: np.ndarray, meta_data: MetaData) -> None:
        self.frame = frame
        self.meta_data = meta_data

    def save_frame(self, image_save_dirpath: Path) -> None:
        filepath = Path(image_save_dirpath) / self.meta_data.filepath
        # ディレクトリが存在しない場合は作成する
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cv2.imwrite(filepath, self.frame)
        logger.info("Image saved: %s", filepath)


class MetaCamera(Camera):
    def __init__(self, cap, session_id, camera_index, filepath_manager):
        super().__init__(cap)
        self.session_id = session_id
        self.camera_index = camera_index
        self.filepath_manager = filepath_manager

    def read_meta_frame(self):
        frame = self.read_frame()
        meta_data = self._get_meta_data()
        return MetaFrame(frame, meta_data)

    def _get_meta_data(self) -> MetaFrame:
        """ フレームをキャプチャして MetaFrame オブジェクトを返す """
        timestamp = datetime.now(timezone.utc)
        filepath = self.filepath_manager.get_frame_filepath(timestamp)
        meta_data = MetaData(
            session_id=self.session_id,
            camera_index=self.camera_index,
            timestamp=timestamp,
            filepath=filepath
        )
        return meta_data


class MetaCameraManager(CameraManager):
    def __init__(self, config: DataAcquisitionConfig,
                 camera_config: CameraConfig,
                 session_id: str,
                 filepath_manager: FilePathManager) -> None:
        super().__init__(camera_config)
        self.frame_reader = None
        self.config = config
        self.session_id = session_id
        self.filepath_manager = filepath_manager

    def __enter__(self) -> 'MetaCameraManager':
        super().__enter__()
        return self

    def get_reader(self) -> MetaCamera:
        if self.cap is None:
            raise RuntimeError("Recording not started.")
        return MetaCamera(self.cap, self.session_id, self.index, self.filepath_manager)

    def __exit__(self, exc_type, exc_value, trace_back) -> None:
        if self.frame_reader is not None:
            logger.info("Acquisition stopped.")
            super().__exit__(exc_type, exc_value, trace_back)
