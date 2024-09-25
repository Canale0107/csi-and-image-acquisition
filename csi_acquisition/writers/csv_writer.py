import io
import os
import csv
import logging

from csi_acquisition.csi.meta_csi_data import MetaCsiData, meta_csi_data_index
from csi_acquisition.writers.abstract_writer import DataWriter, WriterManager


logger = logging.getLogger(__name__)


class CSVWriter(DataWriter):
    def __init__(self, file: io.TextIOWrapper) -> None:
        self.writer = csv.DictWriter(
            file,
            fieldnames=meta_csi_data_index
        )
        self.writer.writeheader()

    def write_data(self, meta_csi_data: MetaCsiData) -> None:
        """ CSVにデータを書き込む """

        if meta_csi_data:
            row = meta_csi_data.to_dict()

            self.writer.writerow(row)
            logger.debug('Meta data written to CSV: %s', row)


class CSVWriterManager(WriterManager):
    def __init__(self, csv_filepath) -> None:
        self.filepath = csv_filepath
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
