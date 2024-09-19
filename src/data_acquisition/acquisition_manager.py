import time
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List
import threading
from contextlib import ExitStack

import cv2

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.camera import CameraManager, FrameWithMetaData, MetaData
from src.data_acquisition.file_manager import FilePathManager
from src.writers import DataWriter, WriterManager, CSVWriterManager, InfluxDBWriterManager


logger = logging.getLogger(__name__)


class DataAcquisitionManager():
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
                 camera_manager: CameraManager, filepath_manager: FilePathManager,
                 data_managers: List[WriterManager], stop_event: threading.Event) -> None:
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self.filepath_manager = filepath_manager
        self.data_managers = data_managers
        self.stop_event = stop_event

    def capture_frame_with_meta_data(self) -> FrameWithMetaData:
        """ フレームをキャプチャして FrameWithMetaData オブジェクトを返す """
        ret, frame = self.camera_manager.cap.read()
        if not ret:
            raise RuntimeError("Failed to capture frame from camera.")
        frame = cv2.flip(frame, 1)  # 画像の左右反転
        timestamp = datetime.now(timezone.utc)
        filepath = self.filepath_manager.get_filepath(timestamp)
        meta_data = MetaData(
            session_id=self.session_id,
            camera_index=self.camera_manager.config.camera_index,
            timestamp=timestamp,
            filepath=filepath
        )
        return FrameWithMetaData(frame, meta_data)

    def save_and_write_frame(self, frame_with_meta_data: FrameWithMetaData, 
                             writers: List[DataWriter]) -> None:
        """ イメージを保存し、データを書き込む """
        frame_with_meta_data.save(self.config.data_dirpath)
        for writer in writers:
            try:
                writer.write_data(frame_with_meta_data.meta_data)
            except Exception as e:
                logger.error("Failed to write data: %s", e)

    def handle_error(self, e: Exception) -> None:
        """ エラーハンドリング """
        logger.error("Error during acquisition: %s", e)

    def start_acquisition(self) -> None:
        """ データ取得の開始 """
        with ExitStack() as stack:
            stack.enter_context(self.camera_manager)

            writers = []
            for data_manager in self.data_managers:
                data_manager = stack.enter_context(data_manager)
                writer = data_manager.get_writer()
                writers.append(writer)

            # カメラのFPSに基づいてスリープ時間を計算 (秒)
            fps = self.camera_manager.config.fps
            sleep_time = 1.0 / fps  # 1フレームの取得に要する時間 (秒)
            next_frame_time = time.time() + sleep_time  # 最初のフレーム取得時間を設定

            try:
                while not self.stop_event.is_set():
                    try:
                        frame_with_meta_data = self.capture_frame_with_meta_data()  # フレームをキャプチャ
                        self.save_and_write_frame(frame_with_meta_data, writers)  # イメージを保存
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
                        session_id: str, csv_filepath: Path):
    try:
        camera_manager = CameraManager(camera_config)
        csv_manager = CSVWriterManager(csv_filepath)
        influxdb_manager = InfluxDBWriterManager(influxdb_config, session_id)
        filepath_manager = FilePathManager(session_id, camera_config.camera_index)
        return camera_manager, csv_manager, influxdb_manager, filepath_manager
    except Exception as e:
        logger.error("Initialization failed for camera %d: %s", camera_config.camera_index, e)
        raise


def get_data_managers(data_acquisition_config: DataAcquisitionConfig, 
                      csv_manager: WriterManager,
                      influxdb_manager: WriterManager) -> List[WriterManager]:
    return [
        manager for manager, enabled in zip(
            [csv_manager, influxdb_manager],
            [data_acquisition_config.save_to_csv, data_acquisition_config.send_to_db]
        )
        if enabled
    ]


def run_acquisition_for_camera(camera_config: CameraConfig,
                               data_acquisition_config: DataAcquisitionConfig,
                               influxdb_config: InfluxDBConfig,
                               session_id: str, stop_event: threading.Event) -> None:
    """ カメラごとにデータ取得を行う """

    csv_filepath = (
        Path(data_acquisition_config.data_dirpath)
        / session_id
        / f'camera{camera_config.camera_index}'
        / 'meta_data.csv'
    )

    # マネージャーの初期化
    camera_manager, csv_manager, influxdb_manager, filepath_manager = initialize_managers(
        camera_config, influxdb_config, session_id, csv_filepath)

    # データマネージャーの設定
    data_managers = get_data_managers(data_acquisition_config, csv_manager, influxdb_manager)

    data_acquisition_manager = DataAcquisitionManager(
        data_acquisition_config,
        session_id,
        camera_manager,
        filepath_manager,
        data_managers, stop_event
    )

    try:
        data_acquisition_manager.start_acquisition()
    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise
