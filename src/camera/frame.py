import os
from datetime import datetime
import logging
from pathlib import Path

from pydantic import BaseModel
import numpy as np
import cv2


logger = logging.getLogger(__name__)


class MetaData(BaseModel):
    session_id: str
    camera_index: int
    timestamp: datetime
    filepath: Path


class FrameWithMetaData:
    def __init__(self, frame: np.ndarray, meta_data: MetaData) -> None:
        self.frame = frame
        self.meta_data = meta_data

    def save_frame(self, image_save_dirpath: Path) -> None:
        filepath = Path(image_save_dirpath) / self.meta_data.filepath
        # ディレクトリが存在しない場合は作成する
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cv2.imwrite(filepath, self.frame)
        logger.info("Image saved: %s", filepath)