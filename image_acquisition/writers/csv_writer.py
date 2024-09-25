import io
import os
import csv
import logging

from image_acquisition.camera import MetaData
from image_acquisition.writers import DataWriter, WriterManager
from image_acquisition.utils import FilePathManager

logger = logging.getLogger(__name__)


class CSVWriter(DataWriter):
    def __init__(self, file: io.TextIOWrapper) -> None:
        self.writer = csv.DictWriter(
            file,
            fieldnames=['filepath', 'timestamp']
        )
        self.writer.writeheader()

    def write_data(self, meta_data: MetaData) -> None:
        """ CSVにデータを書き込む """

        meta_data = {
            "timestamp": float(meta_data.timestamp.timestamp()),
            "filepath": str(meta_data.filepath)
        }

        self.writer.writerow(meta_data)
        logger.debug('Meta data written to CSV: %s', meta_data)


class CSVWriterManager(WriterManager):
    def __init__(self, filepath_manager: FilePathManager) -> None:
        self.filepath = filepath_manager.csv_filepath
        self.file = None
        self.writer = None

    def __enter__(self) -> 'CSVWriterManager':
        """ 一度だけCSVファイルをオープン """
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            self.file = open(self.filepath, mode='w', newline='', encoding='utf-8', buffering=10*1024)
            logger.info('CSV file opened: %s', self.filepath)

        except Exception:
            logger.error('Error occuring while opening CSV file.')
            raise

        return self

    def get_writer(self) -> CSVWriter:
        """ CSVWriterインスタンスを返す """
        if self.file is None:
            raise RuntimeError("CSV file is not opened.")
        return CSVWriter(self.file)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """ ファイルを閉じる """
        if self.file:
            self.file.close()

        logger.info('CSV file %s closed.', self.filepath)
