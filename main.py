from datetime import datetime
import logging
import threading
import time

import image_acquisition
import csi_acquisition

from logging_config import setup_logging, setup_root_logging

def get_session_id() -> str:
    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    return session_id


def main() -> None:
    """
    Main function that coordinates the image and CSI data acquisition process across multiple cameras and CSI sources.
    """

    session_id = get_session_id()
    log_level = logging.INFO

    # Setup loggers for both image and CSI acquisition processes
    setup_root_logging(log_level)
    setup_logging(session_id, log_level)

    # Initialize runners for image and CSI acquisition
    image_acquisition_runner = image_acquisition.Runner(session_id)
    csi_acquisition_runner = csi_acquisition.Runner(session_id)

    # Start separate threads for image and CSI acquisition
    image_thread = threading.Thread(target=image_acquisition_runner.start)
    csi_thread = threading.Thread(target=csi_acquisition_runner.start)

    try:
        logging.info('Start acquisition process')

        # Start both threads
        image_thread.start()
        csi_thread.start()

        # Keep the main thread running to allow keyboard interrupt to stop the acquisition
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logging.info("Keyboard interrupt received. Stopping the acquisition runners...")
        image_acquisition_runner.stop()
        csi_acquisition_runner.stop()

        # Wait for threads to finish
        image_thread.join()
        csi_thread.join()
        logging.info("Acquisition stopped.")

if __name__ == "__main__":
    main()