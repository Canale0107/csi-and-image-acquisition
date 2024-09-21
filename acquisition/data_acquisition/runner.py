import time
from pathlib import Path
from typing import List
import threading
import logging

from yaml import YAMLError
from pydantic import ValidationError

from acquisition.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig, load_configs
from acquisition.writers import CSVWriterManager, InfluxDBWriterManager
from acquisition.camera import MetaCameraManager
from acquisition.data_acquisition.acquirer_manager import DataAcquirerManager
from acquisition.utils import FilePathManager

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, session_id: str, config_path: str = "config.yml"):
        self.session_id = session_id
        logger.info("Initializing Runner with session_id: %s", self.session_id)
        self.config = self._load_config(config_path)
        logger.info("Runner initialized successfully.")

    def _load_config(self, config_path: Path) -> dict:
        try:
            config_path = "config.yml"
            config = load_configs(config_path)
            logger.info('Succeeded to load all configs.')

        except (FileNotFoundError, YAMLError, ValidationError) as e:
            logger.error("Failed to load configs: %s", e)
            raise
        
        return config

    def start(self):
        logger.info("Runner starting...")
        manager = RunnerManager(self.session_id, self.config)
        manager.run_for_multiple_cameras()
        logger.info("Runner has finished execution.")


class RunnerManager:
    def __init__(self, session_id: str, config: dict):
        self.session_id = session_id
        self.config = config
        self.stop_event = threading.Event()
        self.threads = []

    def run_for_multiple_cameras(self):
        camera_configs = self.config.get('cameras', [])
        if not camera_configs:
            logger.error("No camera configurations found.")
            return

        # Create threads for each camera
        for camera_config in self.config['cameras']:
            thread = threading.Thread(target=self._run_for_camera,args=(camera_config,))
            self.threads.append(thread)

        # Start all threads:
        self._start_threads()
        self._monitor_threads()
        logger.info("All camera acquisitions have completed.")
    
    def _start_threads(self):
        for thread in self.threads:
            thread.start()
            logger.debug('thread %s started.', thread)

    def _monitor_threads(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down all camera acquisitions.")
            self.cleanup_acquisition()

        logger.info("All camera acquisitions have completed.")

    def cleanup_acquisition(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join()
        logger.info("All threads have been joined.")

    def _setup_managers(self, camera_config: CameraConfig):
        data_acquisition_config = self.config['data_acquisition']
        writers_config = self.config['writers']

        image_dirpath = (
            Path(data_acquisition_config.data_dirpath)
            / self.session_id
            / f'camera{camera_config.camera_index}'
        )

        csv_filepath = (
            Path(data_acquisition_config.data_dirpath)
            / self.session_id
            / f'camera{camera_config.camera_index}'
            / 'meta_data.csv'
        )

        filepath_manager = FilePathManager(image_dirpath, csv_filepath)

        # Meta Camera manager setup
        meta_camera_manager = MetaCameraManager(
            data_acquisition_config,
            camera_config,
            self.session_id,
            filepath_manager
        )

        # Writer managers setup
        writer_managers_and_flags = [
            (CSVWriterManager(filepath_manager), data_acquisition_config.save_to_csv),
            (InfluxDBWriterManager(writers_config['influxdb']), data_acquisition_config.send_to_db)
        ]

        writer_managers = [manager for manager, enabled in writer_managers_and_flags if enabled]

        return {
            'filepath': filepath_manager,
            'meta_camera': meta_camera_manager,
            'writers': writer_managers
        }

    def _run_for_camera(
        self,
        camera_config: CameraConfig) -> None:
        """ カメラごとにデータ取得を行う """

        managers = self._setup_managers(camera_config)

        try:
            acquirer_manager = DataAcquirerManager(
                DataAcquisitionConfig,
                self.session_id,
                managers['filepath'],
                managers['meta_camera'],
                managers['writers']
            )

            self._acquire_data(acquirer_manager, camera_config)

        except Exception as e:
            logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
            raise

    def _acquire_data(self, acquirer_manager, camera_config):
        fps = camera_config.fps
        sleep_time = 1.0 / fps
        next_frame_time = time.time() + sleep_time
        frame_count = 0
        log_interval = 1  # 最初は1フレームごとにログを出力
        max_log_interval = 1024
        with acquirer_manager as manager:
            acquirer = manager.get_acquirer()
            try:
                logger.info("Camera %d: Starting data acquisition. Press Ctrl + C to stop the process.", camera_config.camera_index)
                while not self.stop_event.is_set():
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