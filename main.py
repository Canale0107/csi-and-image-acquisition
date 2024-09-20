"""
This script manages the acquisition of images from multiple cameras simultaneously,
saves the images to disk, and logs metadata (such as session ID, camera index, image path, 
and timestamp) to both CSV and InfluxDB. The configuration for the data acquisition, cameras, 
and InfluxDB is loaded from YAML files.

Main functionalities:
- Initialize and start a separate thread for each camera to handle image acquisition.
- Manage a unique session ID for each run, based on the current timestamp.
- Capture and save images, and store metadata such as image paths and timestamps.
- Handle graceful shutdown via a stop event when interrupted by the user (Ctrl+C).
- Log important events and errors during the execution process.

Modules used:
- `src.config`: For loading YAML configuration files (camera settings, data acquisition settings, InfluxDB credentials).
- `src.data_acquisition`: For managing the acquisition process for each camera.
- `logging`: For logging information, errors, and events.
- `threading`: For running image acquisition in parallel across multiple cameras.
- `pydantic`: For validating configuration files.
- `yaml`: For parsing YAML configuration files.

To run:
    python3 main.py

To stop the acquisition, use Ctrl+C.
"""

import time
import threading
from datetime import datetime

from yaml import YAMLError
from pydantic import ValidationError

from src.config import load_configs
from src.logger import setup_logger
from src.data_acquisition import run_acquisition_for_camera


logger = setup_logger()


def main() -> None:
    """
    Main function that coordinates the image acquisition process across multiple cameras.

    Steps:
    1. Load configurations for data acquisition, cameras, and InfluxDB from YAML files.
       - Handles errors in case configuration files are missing or invalid.
    2. Generate a unique session ID based on the current timestamp.
    3. Create and start a separate thread for each camera defined in the configuration.
       - Each thread is responsible for acquiring images and logging metadata.
    4. Keep the main thread alive and allow the user to interrupt the process with Ctrl+C.
       - When interrupted, signal all acquisition threads to stop by setting a stop event.
    5. Wait for all threads to finish and ensure that all acquisitions are completed before exiting.

    Logging:
    - Logs events, including errors during configuration loading and shutdown of camera acquisition.

    Raises:
    - None (all exceptions are caught and logged within the function).

    Usage:
        Call this function directly to start the image acquisition process:
            python3 main.py
    """

    try:
        data_acquisition_config, camera_configs, influxdb_config = load_configs()
        logger.info('Succeeded to load all configs.')

    except (FileNotFoundError, YAMLError, ValidationError) as e:
        logger.error("Failed to load configs: %s", e)
        return

    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    stop_event = threading.Event()
    threads = []

    for camera_config in camera_configs:
        thread = threading.Thread(
            target=run_acquisition_for_camera,
            args=(camera_config, data_acquisition_config, influxdb_config, session_id, stop_event)
        )
        threads.append(thread)

    for thread in threads:
        thread.start()
        logger.info('thread %s started.', thread)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down all camera acquisitions.")
        stop_event.set()  # Signal all threads to stop

    for thread in threads:
        thread.join()

    logger.info("All camera acquisitions have completed.")


if __name__ == "__main__":
    main()
