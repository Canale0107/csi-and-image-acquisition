import time
from pathlib import Path
from typing import List
import threading
import logging

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.writers import WriterManager, CSVWriterManager, InfluxDBWriterManager
from src.camera import MetaCameraManager
from src.data_acquisition.acquirer_manager import DataAcquirerManager
from src.utils import FilePathManager


logger = logging.getLogger(__name__)


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

    meta_camera_manager = MetaCameraManager(
        data_acquisition_config,
        camera_config,
        session_id,
        filepath_manager
    )

    # マネージャーの初期化
    writer_managers_and_flags = [
        (CSVWriterManager(filepath_manager), data_acquisition_config.save_to_csv),
        (InfluxDBWriterManager(influxdb_config), data_acquisition_config.send_to_db)
    ]

    writer_managers = [manager for manager, enabled in writer_managers_and_flags if enabled]

    try:
        fps = meta_camera_manager.fps
        sleep_time = 1.0 / fps
        next_frame_time = time.time() + sleep_time

        acquirer_manager = DataAcquirerManager(
            DataAcquisitionConfig,
            session_id,
            filepath_manager,
            meta_camera_manager,
            writer_managers
        )

        with acquirer_manager as manager:
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
