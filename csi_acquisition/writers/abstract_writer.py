from abc import ABC, abstractmethod

class DataWriter(ABC):

    @abstractmethod
    def write_data(self, meta_csi_data) -> None:
        pass

class WriterManager(ABC):

    @abstractmethod
    def get_writer(self) -> DataWriter:
        pass

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass
