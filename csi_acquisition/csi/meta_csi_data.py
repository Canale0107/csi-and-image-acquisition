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

    '''
    - rssi (int): Received Signal Strength Indicator (RSSI) of the packet in dBm.
    - rate (int): PHY rate encoding of the packet. Valid for non HT (11bg) packets.
    - sig_mode (int): 0 for non HT (11bg), 1 for HT (11n), 3 for VHT (11ac) packets.
    - mcs_index (int): Modulation Coding Scheme for HT (11n) packets, ranges from 0 to 76.
    - bandwidth (int): Channel Bandwidth. 0 for 20MHz, 1 for 40MHz.
    - smoothing: reserve
    - not_sounding: reserve
    - aggregation (int): 0 for MPDU, 1 for AMPDU packets.
    - stbc (int): Space Time Block Code. 0 for non-STBC, 1 for STBC packets.
    - fec_coding (int): Indicates if LDPC is used for 11n packets.
    - sgi (int): Short Guide Interval. 0 for Long GI, 1 for Short GI.
    - noise_floor (int): Noise floor of the RF module in 0.25dBm units.
    - ampdu_cnt (int): Number of AMPDU subframes.
    - channel (int): Primary channel the packet was received on.
    - secondary_channel (int): Secondary channel. 0 for none, 1 for above, 2 for below.
    - local_timestamp (int): Local time when the packet was received in microseconds.
    - ant (int): Antenna number. 0 for WiFi antenna 0, 1 for WiFi antenna 1.
    - sig_len (int): Length of the packet including Frame Check Sequence (FCS).
    - rx_state (int): State of the packet. 0 for no error, others represent error codes.
    '''

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