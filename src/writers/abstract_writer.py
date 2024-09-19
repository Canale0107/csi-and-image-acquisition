from typing import Any
from abc import ABC, abstractmethod


class DataWriter(ABC):
    @abstractmethod
    def write_data(self, meta_data: Any) -> None:
        """メタデータを適切な書き込み先に保存する抽象メソッド"""


class DataManager(ABC):
    @abstractmethod
    def get_writer(self) -> DataWriter:
        """Writerインスタンスを返す抽象メソッド"""
