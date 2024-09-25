from datetime import datetime
from typing import List

from pydantic import BaseModel, ValidationError

class MetaCsiData(BaseModel):
    type: str
    role: str
    mac_addr: str
    rssi: int
    rate: int
    sig_mode: int
    mcs_index: int
    bandwidth: int
    smoothing: int
    not_sounding: int
    aggregation: int
    stbc: int
    fec_coding: int
    sgi: int
    noise_floor: int
    ampdu_cnt: int
    channel: int
    secondary_channel: int
    local_timestamp: int
    ant: int
    sig_len: int
    rx_state: int
    real_time_set: int
    real_timestamp: float
    len: int
    csi_data: List[int]
    timestamp: datetime

    def to_dict(self):
        # csi_dataとtimestampの変換処理を専用メソッドに分離
        return {
            **self.model_dump(exclude={"timestamp", "csi_data"}),
            'csi_data': self.format_csi_data(),
            'timestamp': self.timestamp_to_unix()
        }

    def format_csi_data(self):
        # csi_dataのリストを文字列に変換する処理
        return '[' + ' '.join(map(str, self.csi_data)) + ']'

    def timestamp_to_unix(self):
        # datetimeオブジェクトをUnixタイムスタンプに変換
        return self.timestamp.timestamp()

meta_csi_data_index = list(MetaCsiData.model_fields.keys())