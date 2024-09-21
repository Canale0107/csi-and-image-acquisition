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
- `yaml`: For parsing YAML configuration files.
- `pydantic`: For validating configuration files.
- `src.config`: For loading YAML configuration files (camera settings, data acquisition settings, InfluxDB credentials).
- `src.data_acquisition`: For managing the acquisition process for each camera.
- `src.logger`: For logging information, errors, and events.

To run:
    python3 main.py

To stop the acquisition, use Ctrl+C.
"""

from acquisition import Runner


def main() -> None:
    """
    Main function that coordinates the image acquisition process across multiple cameras.

    Steps:
    1. Load configurations for data acquisition, cameras, and InfluxDB from YAML files.
       - Handles errors in case configuration files are missing or invalid.
    2. Generate a unique session ID based on the current timestamp.
    3. Start acquisition and allow the user to interrupt the process with Ctrl+C.

    Usage:
        Call this function directly to start the image acquisition process:
            python3 main.py
    """

    runner = Runner()
    runner.start()

if __name__ == "__main__":
    main()
