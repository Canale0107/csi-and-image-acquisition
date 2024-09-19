import time
import logging
import threading
from datetime import datetime

from src.config import load_configs
from src.data_acquisition import run_acquisition_for_camera


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


def main() -> None:
    try:
        data_acquisition_config, camera_configs, influxdb_config = load_configs()

    except Exception as e:
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
