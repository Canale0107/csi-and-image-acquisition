import time
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List
import threading
from contextlib import ExitStack

import cv2

from src.config.config_loader import DataAcquisitionConfig, CameraConfig, DBConfig
from src.camera.camera_manager import CameraManager
from src.camera.image import Image, ImageMetaData
from .file_manager import FilePathManager
from src.writers.abstract_writer import DataManager
from src.writers.csv_writer import CSVManager
from src.writers.influxdb_writer import InfluxDBManager

logger = logging.getLogger(__name__)

class DataAcquisitionManager():
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
                camera_manager: CameraManager, filepath_manager: FilePathManager,
                data_managers: List[DataManager], stop_event: threading.Event) -> None:
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self.filepath_manager = filepath_manager
        self.data_managers = data_managers
        self.stop_event = stop_event
        self._running = False

    def stop_acquisition(self) -> None:
        self._running = False

    def start_acquisition(self) -> None:
        """ データ取得の開始 """

        image_save_dirpath = self.config.data_dirpath

        with ExitStack() as stack:
            camera_manager = stack.enter_context(self.camera_manager)

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
                self._running = True
                while self._running and not self.stop_event.is_set():
                    try:
                        ret, frame = camera_manager.cap.read()
                        if not ret:
                            raise RuntimeError("Failed to capture frame from camera.")
                        
                        frame = cv2.flip(frame, 1)

                        timestamp = datetime.now(timezone.utc)
                        filepath = self.filepath_manager.get_filepath(timestamp)
                        meta_data = ImageMetaData(
                            session_id = self.session_id,
                            camera_index = self.camera_manager.config.camera_index,
                            timestamp = timestamp,
                            filepath = filepath)
                        
                        image = Image(frame, meta_data)

                        image.save(image_save_dirpath)
                        for writer in writers:
                            try:
                                writer.write_data(meta_data)
                            except Exception as e:
                                logger.error("Failed to write data: %s", e)

                        # 次のフレーム取得までの時間を計算し、必要ならスリープ
                        time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                        next_frame_time += sleep_time  # 次のフレーム取得時間を更新

                    except Exception as e:
                        logger.error("Error capturing image: %s", e)
                        raise

            except Exception as e:
                logger.error("Error during acquisition: %s", e)
                self.stop_acquisition()

            finally:
                self.stop_acquisition()


def run_acquisition_for_camera(camera_config: CameraConfig, data_acquisition_config: DataAcquisitionConfig, db_config: DBConfig, session_id: str, stop_event: threading.Event) -> None:
    """ カメラごとにデータ取得を行う """
    csv_filepath = Path(data_acquisition_config.data_dirpath) / session_id / f'camera{camera_config.camera_index}' / 'meta_data.csv'

    try:
        camera_manager = CameraManager(camera_config)
        csv_manager = CSVManager(csv_filepath)
        influx_db_manager = InfluxDBManager(db_config, session_id)
        filepath_manager = FilePathManager(session_id, camera_config.camera_index)

    except Exception as e:
        logger.error("Initialization failed for camera %d: %s", camera_config.camera_index, e)
        raise

    data_managers = []

    if data_acquisition_config.save_to_csv:
        data_managers.append(csv_manager)

    if data_acquisition_config.send_to_db:
        data_managers.append(influx_db_manager)

    data_acquisition_manager = DataAcquisitionManager(data_acquisition_config, session_id, camera_manager, filepath_manager, data_managers, stop_event)

    try:
        data_acquisition_manager.start_acquisition()

    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise
