import time
from pathlib import Path
from typing import List
import threading
import logging

from yaml import YAMLError
from pydantic import ValidationError

from image_acquisition.config import ImageAcquisitionConfig, CameraConfig, InfluxDBConfig, Config, load_configs
from image_acquisition.writers import CSVWriterManager, InfluxDBWriterManager
from image_acquisition.camera import MetaCameraManager
from image_acquisition.main.acquirer_manager import ImageAcquirerManager
from image_acquisition.utils import FilePathManager

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, session_id: str, config_path: str = "config.yml"):
        self.session_id = session_id
        logger.info("Initializing Runner with session_id: %s", self.session_id)
        self.config = self._load_config(config_path)
        self.manager = None
        logger.info("Runner initialized successfully.")

    def _load_config(self, config_path: str) -> Config:
        try:
            config = load_configs(config_path)
            logger.info('Succeeded to load all configs.')

        except (FileNotFoundError, YAMLError, ValidationError) as e:
            logger.error("Failed to load configs: %s", e)
            raise
        
        return config

    def start(self):
        logger.info("Runner starting...")
        self.manager = RunnerManager(self.session_id, self.config)
        self.manager.run_for_multiple_cameras()
    
    def stop(self):
        if self.manager:
            logger.info("Stopping Runner...")
            self.manager.cleanup_acquisition()  # Managerを通じてカメラ停止処理を実行
            logger.info("Runner stopped successfully.")
        else:
            logger.warning("Runner has not been started yet or manager is missing.")


class RunnerManager:
    def __init__(self, session_id: str, config: Config):
        self.session_id = session_id
        self.config = config
        self.stop_event = threading.Event()
        self.threads = []

    def run_for_multiple_cameras(self):
        camera_configs = self.config.cameras
        if not camera_configs:
            logger.error("No camera configurations found.")
            return

        # Create threads for each camera
        for camera_config in self.config.cameras:
            thread = threading.Thread(target=self._run_for_camera,args=(camera_config,))
            self.threads.append(thread)

        # Start all threads:
        self._start_threads()

    def _start_threads(self):
        for thread in self.threads:
            thread.start()
            logger.debug('thread %s started.', thread)

    def cleanup_acquisition(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join()
        logger.info("All threads have been joined.")

    def _setup_managers(self, camera_config: CameraConfig):
        image_acquisition_config = self.config.image_acquisition
        writers_config = self.config.writers

        image_dirpath = (
            Path(image_acquisition_config.data_dirpath)
            / self.session_id
            / f'camera{camera_config.camera_index}'
        )

        csv_filepath = (
            Path(image_acquisition_config.data_dirpath)
            / self.session_id
            / f'camera{camera_config.camera_index}'
            / 'meta_data.csv'
        )

        filepath_manager = FilePathManager(image_dirpath, csv_filepath)

        # Meta Camera manager setup
        meta_camera_manager = MetaCameraManager(
            image_acquisition_config,
            camera_config,
            self.session_id,
            filepath_manager
        )

        # Writer managers setup
        writer_managers_and_flags = [
            (CSVWriterManager(filepath_manager), image_acquisition_config.save_to_csv),
            (InfluxDBWriterManager(writers_config['influxdb']), image_acquisition_config.send_to_db)
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
            acquirer_manager = ImageAcquirerManager(
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
        frames_in_last_second = 0
        start_time = time.time()
        
        with acquirer_manager as manager:
            acquirer = manager.get_acquirer()
            try:
                logger.info("Camera %d: Starting data acquisition. Press Ctrl + C to stop the process.", camera_config.camera_index)
                while not self.stop_event.is_set():
                    try:
                        acquirer.acquire_meta_frame()
                        frame_count += 1
                        frames_in_last_second += 1

                        current_time = time.time()
                        
                        # 1秒経過ごとにフレーム数とFPSをログ出力
                        if current_time - start_time >= 1.0:
                            logger.info("Camera %d: Acquisition in progress: %d frames captured so far. Current FPS: %.2f", 
                                        camera_config.camera_index, frame_count, frames_in_last_second / (current_time - start_time))
                            
                            # タイミングと1秒間のフレーム数をリセット
                            start_time = current_time
                            frames_in_last_second = 0

                        time.sleep(max(0, next_frame_time - current_time))
                        next_frame_time += sleep_time

                    except Exception as e:
                        logger.error("Error during acquisition: %s", e)
                        break

            finally:
                logger.info("Camera %d: Acquisition stopped. Total frames captured: %d", camera_config.camera_index, frame_count)
