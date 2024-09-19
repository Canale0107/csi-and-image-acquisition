import io
import os
import csv
import logging

from src.camera.image import ImageMetaData
from src.writers import DataWriter, DataManager


logger = logging.getLogger(__name__)


class CSVWriter(DataWriter):
    def __init__(self, file: io.TextIOWrapper) -> None:
        self.writer = csv.DictWriter(file, fieldnames=['session_id', 'camera_index', 'filepath', 'timestamp'])
        self.writer.writeheader()

    def write_data(self, meta_data: ImageMetaData) -> None:
        """ CSVにデータを書き込む """

        meta_data = {
            "session_id": str(meta_data.session_id),
            "camera_index": int(meta_data.camera_index),
            "timestamp": float(meta_data.timestamp.timestamp()),
            "filepath": str(meta_data.filepath)
        }

        self.writer.writerow(meta_data)


class CSVManager(DataManager):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.file = None
        self.writer = None

    def __enter__(self) -> 'CSVManager':
        """ 一度だけCSVファイルをオープン """
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.file = open(self.filepath, mode='w', newline='', encoding='utf-8', buffering=10*1024)
        return self

    def get_writer(self) -> CSVWriter:
        """ CSVWriterインスタンスを返す """
        if self.file is None:
            raise RuntimeError("CSVファイルがオープンされていません。")
        return CSVWriter(self.file)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """ ファイルを閉じる """
        if self.file:
            self.file.close()
