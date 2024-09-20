import time
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List
import threading
import traceback
from contextlib import ExitStack

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.camera import FrameReader, CameraManager, FrameWithMetaData, MetaData
from src.utils.file_manager import FilePathManager
from src.writers import DataWriter, WriterManager, CSVWriterManager, InfluxDBWriterManager


logger = logging.getLogger(__name__)

'''
class FrameWithMetaDataReader(FrameReader):
    def __init__(self, cap, session_id, camera_index, filepath_manager):
        super().__init__(cap)
        self.session_id = session_id
        self.camera_index = camera_index
        self.filepath_manager = filepath_manager

    def read_frame_with_meta_data(self):
        meta_data = self._get_meta_data()
        frame = self.read_frame()
        return FrameWithMetaData(frame, meta_data)

    def _get_meta_data(self) -> FrameWithMetaData:
        """ フレームをキャプチャして FrameWithMetaData オブジェクトを返す """
        timestamp = datetime.now(timezone.utc)
        filepath = self.filepath_manager.get_frame_filepath(timestamp)
        meta_data = MetaData(
            session_id=self.session_id,
            camera_index=self.camera_index,
            timestamp=timestamp,
            filepath=filepath
        )
        return meta_data


class CameraWithMetaDataManager(CameraManager):
    def __init__(self, config: DataAcquisitionConfig,
                 camera_manager: CameraManager,
                 session_id: str,
                 camera_index: int,
                 fps: int,
                 filepath_manager: FilePathManager) -> None:
        self.frame_reader = None
        self.config = config
        self.camera_manager = camera_manager
        self.session_id = session_id
        self.camera_index = camera_index
        self.fps = fps
        self.filepath_manager = filepath_manager

    def __enter__(self) -> 'FrameWithMetaDataReaderManager':
        self.frame_reader = self.camera_manager.get_reader()
        return self
    
    def get_reader(self) -> FrameWithMetaDataReader:
        if self.frame_reader is None:
            raise RuntimeError("Recording not started.")
        return FrameWithMetaDataReader(self.frame_reader, self.session_id, self.camera_index, self.filepath_manager)

    def __exit__(self, exc_type, exc_value, trace_back) -> None:
        if self.frame_reader is not None:
            logger.info("Acquisition stopped.")
'''


class DataAcquisitionManager:
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
                camera_manager: CameraManager,
                filepath_manager: FilePathManager,
                writer_managers: List[WriterManager], stop_event: threading.Event) -> None:
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self.filepath_manager = filepath_manager
        self.writer_managers = writer_managers
        self.stop_event = stop_event

    def get_meta_data(self) -> FrameWithMetaData:
        """ フレームをキャプチャして FrameWithMetaData オブジェクトを返す """
        timestamp = datetime.now(timezone.utc)
        filepath = self.filepath_manager.get_frame_filepath(timestamp)
        meta_data = MetaData(
            session_id=self.session_id,
            camera_index=self.camera_manager.config.camera_index,
            timestamp=timestamp,
            filepath=filepath
        )
        return meta_data

    def save_meta_data(self, frame_with_meta_data: FrameWithMetaData, 
                             data_writers: List[DataWriter]) -> None:
        """ イメージを保存し、データを書き込む """
        for data_writer in data_writers:
            try:
                data_writer.write_data(frame_with_meta_data.meta_data)
            except Exception as e:
                logger.error("Failed to write data: %s", e)
                traceback.print_exc()  # エラーメッセージを表示
                raise  # エラーを再度発生させてプログラムを停止させる

    def handle_error(self, e: Exception) -> None:
        """ エラーハンドリング """
        logger.error("Error during acquisition: %s", e)

    def start_acquisition(self) -> None:
        """ データ取得の開始 """
        with ExitStack() as stack:
            frame_reader = stack.enter_context(self.camera_manager).get_reader()
            data_writers = [stack.enter_context(wm).get_writer() for wm in self.writer_managers]

            # カメラのFPSに基づいてスリープ時間を計算 (秒)
            fps = self.camera_manager.config.fps
            sleep_time = 1.0 / fps  # 1フレームの取得に要する時間 (秒)
            next_frame_time = time.time() + sleep_time  # 最初のフレーム取得時間を設定

            try:
                while not self.stop_event.is_set():
                    try:
                        frame = frame_reader.read_frame()
                        meta_data = self.get_meta_data()
                        logger.info('meta_data: %s', meta_data)
                        frame_with_meta_data = FrameWithMetaData(frame, meta_data)
                        frame_with_meta_data.save_frame(self.filepath_manager.image_dirpath)
                        self.save_meta_data(frame_with_meta_data, data_writers)

                        # 次のフレーム取得までの時間を計算し、必要ならスリープ
                        time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                        next_frame_time += sleep_time  # 次のフレーム取得時間を更新

                    except Exception as e:
                        self.handle_error(e)
                        break  # エラー時にループを抜ける

            finally:
                logger.info("Acquisition stopped.")


def initialize_managers(camera_config: CameraConfig,
                        influxdb_config: InfluxDBConfig,
                        filepath_manager: FilePathManager):
    try:
        camera_manager = CameraManager(camera_config)
        csv_writer_manager = CSVWriterManager(filepath_manager)
        influxdb_writer_manager = InfluxDBWriterManager(influxdb_config)
        return camera_manager, csv_writer_manager, influxdb_writer_manager
    except Exception as e:
        logger.error("Initialization failed for camera %d: %s", camera_config.camera_index, e)
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
    camera_manager, csv_writer_manager, influxdb_writer_manager = initialize_managers(camera_config, influxdb_config, filepath_manager)

    # データマネージャーの設定
    writer_managers = get_writer_managers(data_acquisition_config, csv_writer_manager, influxdb_writer_manager)

    data_acquisition_manager = DataAcquisitionManager(
        data_acquisition_config,
        session_id,
        camera_manager,
        filepath_manager,
        writer_managers, stop_event
    )

    try:
        data_acquisition_manager.start_acquisition()
    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise
