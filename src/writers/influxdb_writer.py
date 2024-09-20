from datetime import datetime
import logging

from influxdb_client import Point, WritePrecision, WriteApi

from src.config import InfluxDBConfig
from src.camera import MetaData
from src.writers import DataWriter, WriterManager

logger = logging.getLogger(__name__)


class InfluxDBWriter(DataWriter):
    def __init__(self, write_api: WriteApi, bucket: str) -> None:
        self.write_api = write_api
        self.bucket = bucket

    def write_data(self, meta_data: MetaData) -> None:
        """ InfluxDBにデータを書き込む """

        assert isinstance(meta_data.timestamp, datetime), \
            f"Expected timestamp to be datetime, but got {type(meta_data.get('timestamp'))}"

        point = (Point("IMAGE_DATA").tag("session_id", str(meta_data.session_id))
                                    .tag("camera_index", int(meta_data.camera_index))
                                    .field("filepath", str(meta_data.filepath))
                                    .time(meta_data.timestamp, WritePrecision.NS)
        )
        self.write_api.write(bucket=self.bucket, record=point)
        logger.debug("Data written to DB: %s", point.to_line_protocol())


class InfluxDBWriterManager(WriterManager):
    def __init__(self, config: InfluxDBConfig) -> None:
        self.config = config
        self.client = None
        self.write_api = None

    def __enter__(self) -> 'InfluxDBWriterManager':
        """ データ取得開始時に一度だけデータベースに接続 """
        self.client = self.config.get_client()
        self.write_api = self.client.write_api()

        # データベース接続のテスト
        try:
            health = self.client.health()
            logger.info("Connected to InfluxDB, health: %s", health.status)
        except Exception as e:
            logger.error("Failed to connect to database: %s", e)
            raise

        return self

    def get_writer(self) -> InfluxDBWriter:
        """ InfluxDBWriterインスタンスを返す """
        if self.client is None or self.write_api is None:
            raise RuntimeError("Not connected to DB.")
        return InfluxDBWriter(self.write_api, self.config.bucket)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """ データ取得終了時にデータベース接続を閉じる """
        if self.write_api is not None:
            try:
                self.write_api.flush()  # バッチデータを送信
                self.write_api.close()  # write_apiを閉じる

            except Exception as e:
                logger.error("Error while closing write API: %s", e)
                return False

        if self.client is not None:
            self.client.close()

            logger.info('InfluxDB closed.')
