from datetime import datetime, timezone
import logging

from acquisition.config import CameraConfig, DataAcquisitionConfig
from acquisition.camera.camera import  Camera, CameraManager
from acquisition.camera.meta_frame import MetaFrame, MetaData
from acquisition.utils import FilePathManager


logger = logging.getLogger(__name__)


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
