from typing import List
import logging

from src.config import DataAcquisitionConfig
from src.camera import MetaCameraManager, MetaCamera
from src.utils.file_manager import FilePathManager
from src.writers import DataWriter, WriterManager


logger = logging.getLogger(__name__)


class DataAcquirer:
    def __init__(self, meta_camera: MetaCamera, 
                 data_writers: List[DataWriter], 
                 filepath_manager: FilePathManager):
        self.meta_camera = meta_camera
        self.data_writers = data_writers
        self.filepath_manager = filepath_manager

    def acquire_meta_frame(self) -> None:
        """ イメージを保存し、データを書き込む """
        meta_frame = self.meta_camera.read_meta_frame()

        meta_frame.save_frame(self.filepath_manager.image_dirpath)
        for data_writer in self.data_writers:
            try:
                data_writer.write_data(meta_frame.meta_data)
            except Exception as e:
                logger.error("Failed to write data: %s", e)
                raise  # エラーを再度発生させてプログラムを停止させる


class DataAcquirerManager:
    def __init__(self, config: DataAcquisitionConfig, 
                 session_id: str,
                 filepath_manager: FilePathManager,
                 meta_camera_manager: MetaCameraManager,
                 writer_managers: List[WriterManager]) -> None:
        self.config = config
        self.session_id = session_id
        self.filepath_manager = filepath_manager
        self.meta_camera_manager = meta_camera_manager
        self.meta_camera = None
        self.writer_managers = writer_managers
        self.data_writers = None  # __enter__ で初期化される

    def __enter__(self):
        # コンテキストマネージャとしてリソースを初期化
        self.meta_camera = self.meta_camera_manager.__enter__().get_reader()
        self.data_writers = [wm.__enter__().get_writer() for wm in self.writer_managers]
        return self

    def get_acquirer(self) -> DataAcquirer:
        if self.meta_camera is None:
            raise RuntimeError("MetaCamera is not ready.")
        if self.data_writers is None:
            raise RuntimeError("DataWriters is not ready.")

        return DataAcquirer(self.meta_camera, self.data_writers, self.filepath_manager)

    def __exit__(self, exc_type, exc_value, traceback):
        # リソースの解放やログの処理
        logger.info("Releasing resources and stopping acquisition.")
        self.meta_camera_manager.__exit__(exc_type, exc_value, traceback)
        for writer_manager in self.writer_managers:
            writer_manager.__exit__(exc_type, exc_value, traceback)
        if exc_type:
            logger.error("An exception occurred: %s", exc_value)
