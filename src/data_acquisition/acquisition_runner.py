import time
from pathlib import Path
from typing import List, Dict
import threading
import logging

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.writers import CSVWriterManager, InfluxDBWriterManager
from src.camera import MetaCameraManager
from src.data_acquisition.acquirer_manager import DataAcquirerManager
from src.utils import FilePathManager


logger = logging.getLogger(__name__)


def run_acquisition_for_camera(
        camera_config: CameraConfig,
        data_acquisition_config: DataAcquisitionConfig,
        writers_config: Dict,
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
        (InfluxDBWriterManager(writers_config['influxdb']), data_acquisition_config.send_to_db)
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

        frame_count = 0
        log_interval = 1  # 最初は1フレームごとにログを出力
        max_log_interval = 1024
        with acquirer_manager as manager:
            acquirer = manager.get_acquirer()
            try:
                logger.info("Camera %d: Starting data acquisition. Press Ctrl + C to stop the process.", camera_config.camera_index)
                while not stop_event.is_set():
                    try:
                        acquirer.acquire_meta_frame()
                        frame_count += 1

                        # 指定されたフレーム数に達した場合にログを出力
                        if frame_count >= log_interval:
                            logger.info("Camera %d: Acquisition in progress: %d frames captured so far.", camera_config.camera_index, frame_count)
                            
                            # ログ出力の間隔を指数的に増やす
                            log_interval = min(log_interval*2, max_log_interval)

                        time.sleep(max(0, next_frame_time - time.time()))
                        next_frame_time += sleep_time

                    except Exception as e:
                        logger.error("Error during acquisition: %s", e)
                        break

            finally:
                logger.info("Camera %d: Acquisition stopped. Total frames captured: %d", camera_config.camera_index, frame_count)

    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise

def cleanup_acquisition(threads, stop_event):
    stop_event.set()
    for thread in threads:
        thread.join()
    logger.info("All camera acquisitions have completed.")

def run_acquistion_for_multiple_cameras(
        session_id: str,
        config: Dict):
    stop_event = threading.Event()
    threads = []

    for camera_config in config['cameras']:
        thread = threading.Thread(
            target=run_acquisition_for_camera,
            args=(camera_config, config['data_acquisition'], config['writers'], session_id, stop_event)
        )
        threads.append(thread)

    for thread in threads:
        thread.start()
        logger.debug('thread %s started.', thread)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down all camera acquisitions.")
        cleanup_acquisition(threads, stop_event)

    logger.info("All camera acquisitions have completed.")
