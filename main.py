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

To run:
    python3 main.py

To stop the acquisition, use Ctrl+C.
"""
from datetime import datetime
import logging

import image_acquisition

def get_session_id() -> str:
    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    return session_id


def main() -> None:
    """
    Main function that coordinates the image acquisition process across multiple cameras.
    """

    session_id = get_session_id()
    log_level = logging.INFO
    image_acquisition.setup_logger(session_id, log_level)
    runner = image_acquisition.Runner(session_id)
    runner.start()

if __name__ == "__main__":
    main()
