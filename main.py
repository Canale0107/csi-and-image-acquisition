from datetime import datetime
import logging
import threading
import time

import image_acquisition
import csi_acquisition

from logging_config import setup_logging

def get_session_id() -> str:
    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    return session_id


def log_periodically(interval: int, start_time: float, stop_event: threading.Event):
    """
    Logs the elapsed time every `interval` seconds until the stop_event is set.
    """
    while not stop_event.wait(interval):
        elapsed_time = time.time() - start_time
        logging.info('Elapsed time: %d seconds since acquisition started', int(elapsed_time))

def main() -> None:
    """
    Main function that coordinates the image and CSI data acquisition process across multiple cameras and CSI sources.
    """
    session_id = get_session_id()
    log_level = logging.INFO

    # Setup loggers for both image and CSI acquisition processes
    setup_logging(session_id, log_level)

    # Initialize runners for image and CSI acquisition
    image_acquisition_runner = image_acquisition.Runner(session_id)
    csi_acquisition_runner = csi_acquisition.Runner(session_id)

    # Start separate threads for image and CSI acquisition
    image_thread = threading.Thread(target=image_acquisition_runner.start)
    csi_thread = threading.Thread(target=csi_acquisition_runner.start)

    # Setup the stop event and start logging every 30 seconds
    start_time = time.time()
    stop_event = threading.Event()
    logging_thread = threading.Thread(target=log_periodically, args=(10, start_time, stop_event))

    try:
        logging.info('Start acquisition process')

        # Start both threads
        image_thread.start()
        csi_thread.start()
        logging_thread.start()

        # Keep the main thread running to allow keyboard interrupt to stop the acquisition
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logging.info("Keyboard interrupt received. Stopping the acquisition runners...")
        image_acquisition_runner.stop()
        csi_acquisition_runner.stop()

        # Signal the logging thread to stop and wait for threads to finish
        stop_event.set()
        image_thread.join()
        csi_thread.join()
        logging_thread.join()
        logging.info("Acquisition stopped.")

if __name__ == "__main__":
    main()
