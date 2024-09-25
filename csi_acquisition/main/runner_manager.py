import time
import logging
from pathlib import Path

from yaml import YAMLError
from pydantic import ValidationError

from csi_acquisition.config import load_configs, Config
from csi_acquisition.csi import SerialReaderManager
from csi_acquisition.writers import CSVWriterManager, InfluxDBWriterManager, UdpSenderManager
from csi_acquisition.main.acquirer_manager import CsiAcquirerManager

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, session_id: str, config_path: str = "config.yml"):
        self.session_id = session_id
        logger.info("Initializing Runner with session_id: %s", self.session_id)
        self.config = self._load_config(config_path)
        self.manager = None
        logger.info("Runner initialized successfully.")
    
    def _load_config(self, config_path: str):
        try:
            config = load_configs(config_path)
            logger.info('Succeeded to load all configs.')

        except (FileNotFoundError, YAMLError, ValidationError) as e:
            logger.error("Failed to load configs: %s", e)
            raise
        
        return config
    
    def start(self):
        self.manager = RunnerManager(self.session_id, self.config)
        logger.info("Runner starting...")
        self.manager.run()

    def stop(self):
        if self.manager:
            logger.info("Stopping Runner...")
            self.manager.cleanup_acquisition()
            logger.info("Runner stopped successfully.")
        else:
            logger.warning("Runner has not been started yet or manager is missing.")


class RunnerManager:
    def __init__(self, session_id: str, config: Config):
        self.session_id = session_id
        self.config = config
        self.is_running = False

    def run(self):
        managers = self._setup_managers()

        acquirer_manager = CsiAcquirerManager(
            self.session_id,
            managers['serial'],
            managers['writers']
        )

        self._acquire_data(acquirer_manager)

    def cleanup_acquisition(self):
        self.is_running = False

    def _setup_managers(self):
        csi_acquisition_config = self.config.csi_acquisition
        csv_filepath = Path(csi_acquisition_config.data_dirpath) / self.session_id / f'csi_{self.session_id}.csv'

        serial_reader_manager = SerialReaderManager(self.config.csi)

        writer_managers_and_flags = [
            (CSVWriterManager(csv_filepath), csi_acquisition_config.save_to_csv),
            (InfluxDBWriterManager(self.config.influxdb), csi_acquisition_config.send_to_db),
            (UdpSenderManager(self.config.udp), csi_acquisition_config.send_via_udp)
        ]

        writer_managers = [manager for manager, enabled in writer_managers_and_flags if enabled]

        return {
            'serial': serial_reader_manager,
            'writers': writer_managers
        }

    def _acquire_data(self, acquirer_manager):

        frame_count = 0
        frames_in_last_second = 0
        start_time = time.time()
        with acquirer_manager as manager:
            acquirer = manager.get_acquirer()

            try:
                logger.info("Starting data acquisition. Press Ctrl + C to stop the process.")
                last_data_time = time.time()

                self.is_running = True
                while self.is_running:
                    try:
                        if acquirer.acquirer_meta_csi_data(last_data_time):
                            frame_count += 1
                            frames_in_last_second += 1
                            last_data_time = time.time()

                        if last_data_time - start_time >= 1.0:
                            logger.info('CSI Acquisition in progress: %d frames captured so far. Current FPS: %.2f',
                                        frame_count, frames_in_last_second / (last_data_time - start_time))
                            # タイミングと1秒間のフレーム数をリセット
                            start_time = last_data_time
                            frames_in_last_second = 0

                        time.sleep(0.001)

                    
                    except Exception as e:
                        logger.error("Error during acquisition: %s", e)
                        raise

            finally:
                logger.info("Acquisition stopped. Total frames captured: %d", frame_count)
