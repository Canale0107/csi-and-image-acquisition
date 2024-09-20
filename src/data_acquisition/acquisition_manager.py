import time
import logging
from pathlib import Path
from typing import List
import threading
import traceback
from contextlib import ExitStack

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.camera import MetaCameraManager, MetaCamera, MetaFrame
from src.utils.file_manager import FilePathManager
from src.writers import DataWriter, WriterManager, CSVWriterManager, InfluxDBWriterManager


logger = logging.getLogger(__name__)


class DataAcquirer:
    def __init__(self, meta_camera: MetaCamera, data_writers: List[DataWriter], filepath_manager: FilePathManager):
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
                traceback.print_exc()  # エラーメッセージを表示
                raise  # エラーを再度発生させてプログラムを停止させる


class DataAcquirerManager:
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
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


# TODO: InfluxDBはカメラごとではなく、共通で1つでいいのでは
def initialize_managers(influxdb_config: InfluxDBConfig,
                        filepath_manager: FilePathManager):
    try:
        csv_writer_manager = CSVWriterManager(filepath_manager)
        influxdb_writer_manager = InfluxDBWriterManager(influxdb_config)
        return csv_writer_manager, influxdb_writer_manager
    except Exception as e:
        logger.error("Initialization failed: %e", e)
        raise


def get_writer_managers(data_acquisition_config: DataAcquisitionConfig, 
                      csv_writer_manager: WriterManager,
                      influxdb_writer_manager: WriterManager) -> List[WriterManager]:
    return [
        manager for manager, enabled in zip(
            [csv_writer_manager, influxdb_writer_manager],
            [data_acquisition_config.save_to_csv, data_acquisition_config.send_to_db]
        )
        if enabled
    ]

def run_acquisition_for_camera(camera_config: CameraConfig,
                               data_acquisition_config: DataAcquisitionConfig,
                               influxdb_config: InfluxDBConfig,
                               session_id: str, stop_event: threading.Event) -> None:
    """ カメラごとにデータ取得を行う """

    image_dirpath = (
        Path(data_acquisition_config.data_dirpath)
        / session_id
        / f'camera{camera_config.camera_index}'
    )

    csv_filepath = (
        Path(data_acquisition_config.data_dirpath)
        / session_id
        / f'camera{camera_config.camera_index}'
        / 'meta_data.csv'
    )

    filepath_manager = FilePathManager(image_dirpath, csv_filepath)

    # マネージャーの初期化
    csv_writer_manager, influxdb_writer_manager = initialize_managers(influxdb_config, filepath_manager)

    meta_camera_manager = MetaCameraManager(
        data_acquisition_config,
        camera_config,
        session_id,
        filepath_manager
    )

    # データマネージャーの設定
    writer_managers = get_writer_managers(data_acquisition_config, csv_writer_manager, influxdb_writer_manager)

    try:
        fps = meta_camera_manager.fps
        sleep_time = 1.0 / fps
        next_frame_time = time.time() + sleep_time

        with DataAcquirerManager(
            DataAcquisitionConfig, 
            session_id, 
            filepath_manager, meta_camera_manager, writer_managers) as manager:
            acquirer = manager.get_acquirer()
            try:
                while not stop_event.is_set():
                    try:
                        acquirer.acquire_meta_frame()

                        time.sleep(max(0, next_frame_time - time.time()))
                        next_frame_time += sleep_time

                    except Exception as e:
                        logger.error("Error during acquisition: %s", e)
                        break

            finally:
                logger.info("Acquisition stopped.")

    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise

