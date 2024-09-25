from datetime import datetime
import logging

import numpy as np
from influxdb_client import Point, WritePrecision, WriteApi

from csi_acquisition.config import InfluxDBConfig
from csi_acquisition.csi.meta_csi_data import MetaCsiData
from csi_acquisition.writers.abstract_writer import DataWriter, WriterManager

logger = logging.getLogger(__name__)


EXPECTED_CSV_COLUMN_COUNT = 26
CSI_DATA_LENGTH = 128


class InfluxDBWriter(DataWriter):
    def __init__(self, write_api: WriteApi, bucket: str) -> None:
        self.write_api = write_api
        self.bucket = bucket

    def write_data(self, meta_csi_data: MetaCsiData) -> None:
        """ InfluxDBにデータを書き込む """

        assert isinstance(meta_csi_data.timestamp, datetime), \
            f"Expected timestamp to be datetime, but got {type(meta_csi_data.timestamp)}"

        common_tags = self.create_common_tags(meta_csi_data)
        points = self.create_csi_points(meta_csi_data, common_tags)
        self.write_api.write(bucket=self.bucket, record=points)

    def create_common_tags(self, meta_csi_data: MetaCsiData):

        sig_mode_dict = {
            0: "non HT(11bg)",
            1: "HT(11n)",
            3: "VHT(11ac)"
        }

        bandwidth_dict = {
            0: "20MHz",
            1: "40MHz"
        }

        aggregation_dict = {
            0: "MPDU packet",
            1: "AMPDU packet"
        }

        stbc_dict = {
            0: "non STBC packet",
            1: "STBC packet"
        }

        sgi_dict = {
            0: "Long GI",
            1: "Short GI"
        }

        ant_dict = {
            0: "WiFi antenna 0",
            1: "WiFi antenna 1"
        }
        
        return {
            "role": meta_csi_data.role,
            "mac_addr": meta_csi_data.mac_addr.replace(":","-"),
            "sig_mode": sig_mode_dict[meta_csi_data.sig_mode],
            "bandwidth": bandwidth_dict[meta_csi_data.bandwidth],
            "fec_coding": meta_csi_data.fec_coding,
            "channel": meta_csi_data.channel,
            "secondary_channel": meta_csi_data.secondary_channel,
            "ant": ant_dict[meta_csi_data.ant],
            "sig_len": meta_csi_data.sig_len,
            "rx_state": meta_csi_data.rx_state
        }
    
    def create_point(self, data_type, field_name, field_value, common_tags, timestamp):
        """
        Helper function to create a point with common tags.
        """
        point = (
            Point("CSI_DATA")
            .tag("data_type", data_type)
            .field(field_name, field_value)
            .time(timestamp, WritePrecision.NS)
        )
        for tag, value in common_tags.items():
            point = point.tag(tag, value)
        return point

    def create_csi_points(self, meta_csi_data: MetaCsiData, common_tags: dict):
        rssi = meta_csi_data.rssi
        mcs_index = meta_csi_data.mcs_index
        aggregation = meta_csi_data.aggregation
        ampdu_cnt = meta_csi_data.ampdu_cnt
        sgi = meta_csi_data.sgi
        noise_floor = meta_csi_data.noise_floor
        csi_data = meta_csi_data.csi_data
        timestamp = meta_csi_data.timestamp

        points = []
        points.append(self.create_point("RSSI", "RSSI", rssi, common_tags, timestamp))
        points.append(self.create_point("MCS Index", "mcs_index", mcs_index, common_tags, timestamp))
        points.append(self.create_point("Aggregation", "aggregation", aggregation, common_tags, timestamp))
        points.append(self.create_point("AMPDU Count", "ampdu_count", ampdu_cnt, common_tags, timestamp))
        points.append(self.create_point("SGI", "sgi", sgi, common_tags, timestamp))
        points.append(self.create_point("Noise Floor", "noise_floor", noise_floor, common_tags, timestamp))

        if csi_data and len(csi_data) == CSI_DATA_LENGTH:
            csi = self.csi_data_to_complex_array(csi_data)
            amp, phase = np.abs(csi), np.angle(csi)

            # Create Amplitude and Phase points for each subcarrier
            for i, (a, p) in enumerate(zip(amp, phase)):
                points.append(
                    self.create_point("Amplitude", f"Subcarrier_{i:02d}", a, common_tags, timestamp)
                )
                points.append(
                    self.create_point("Phase", f"Subcarrier_{i:02d}", p, common_tags, timestamp)
                )

        return points
    
    def csi_data_to_complex_array(self, csi_data):
        imaginary = csi_data[::2]
        real = csi_data[1::2]
        return np.array(real) + 1j * np.array(imaginary)


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
