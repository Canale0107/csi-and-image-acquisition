"""
This module defines abstract base classes for managing the writing of metadata
from image acquisition processes. It includes the `DataWriter` and `DataManager` 
classes, which outline the structure for writing metadata to various destinations 
and managing writer instances.

Classes:
- DataWriter: An abstract base class for writing metadata from image acquisition 
              to different storage backends.
- DataManager: An abstract base class for managing and providing instances of 
               `DataWriter`, including context management for resource handling.
"""

from abc import ABC, abstractmethod
from src.camera import ImageMetaData


class DataWriter(ABC):
    """
    Abstract base class responsible for defining the interface for writing image 
    metadata to a specified destination.

    Methods:
    - write_data: Must be implemented by subclasses to handle the actual writing 
                  of metadata.
    """

    @abstractmethod
    def write_data(self, meta_data: ImageMetaData) -> None:
        """
        Abstract method for writing image metadata to the appropriate storage.

        Parameters:
        - meta_data (ImageMetaData): The metadata object containing session information, 
                                     camera details, image path, and timestamp.

        This method must be implemented by any subclass to define how the metadata 
        will be stored (e.g., to a CSV file, database, etc.).
        """


class DataManager(ABC):
    """
    Abstract base class for managing `DataWriter` instances and handling resource 
    management through context management (`__enter__` and `__exit__` methods).

    Methods:
    - get_writer: Must be implemented by subclasses to return an instance of a 
                  `DataWriter` that is responsible for writing metadata.
    - __enter__: Must be implemented by subclasses for context management when 
                 entering a context (e.g., opening resources).
    - __exit__: Must be implemented by subclasses for context management when 
                exiting a context (e.g., closing or cleaning up resources).
    """

    @abstractmethod
    def get_writer(self) -> DataWriter:
        """
        Abstract method for providing a `DataWriter` instance.

        This method must be implemented by any subclass to return a specific writer 
        (e.g., CSV writer, database writer) depending on the backend destination 
        for metadata.

        Returns:
        - DataWriter: An instance of a class that implements the `DataWriter` interface.
        """

    @abstractmethod
    def __enter__(self):
        """
        Abstract method for handling setup or resource allocation when entering a context.

        Subclasses should implement this method to define actions needed when starting 
        a context (e.g., opening database connections, initializing resources).
        """

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Abstract method for handling cleanup or resource deallocation when exiting a context.

        Subclasses should implement this method to define actions needed when exiting 
        a context (e.g., closing database connections, releasing resources).

        Parameters:
        - exc_type: The exception type, if an exception occurred.
        - exc_value: The exception value, if an exception occurred.
        - traceback: The traceback object, if an exception occurred.
        """
