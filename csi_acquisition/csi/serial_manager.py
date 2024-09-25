import re
import time
from datetime import datetime, timezone
import logging
import serial

from csi_acquisition.csi.meta_csi_data import MetaCsiData, meta_csi_data_index

# ロギング設定
logger =  logging.getLogger(__name__)


NO_DATA_SLEEP_DURATION = 1


class SerialReader:
    def __init__(self, serial_connection, no_data_timeout, no_data_sleep_duration):
        self.serial_connection = serial_connection
        self.no_data_timeout = no_data_timeout
        self.no_data_sleep_duration = no_data_sleep_duration
    
    def read_line(self) -> str:
        try:
            line = self.serial_connection.readline().decode('utf-8').strip()
            logger.debug("Read line: %s", line)
            return line
        except UnicodeDecodeError as e:
            logger.debug("Failed to decode line: %s", e)
            return None
        
    def read_valid_line(self):
        line = self.read_line()
        if line:
            if 'CSI_DATA' in line:
                if self.is_valid_line(line):
                    logger.debug("Valid line read: %s", line)
                    return line
                logger.debug("Invalid line: %s", line)
        return None
    
    def _handle_no_data(self, last_data_time):
        logger.debug("No data read from serial port.")
        if time.time() - last_data_time > self.no_data_timeout:
            logger.warning("No data timeout")
            time.sleep(self.no_data_sleep_duration)
            raise TimeoutError("No data received within the specified timeout period.")
    
    def read_meta_csi_data(self, last_data_time):
        line = self.read_valid_line()
        if line:
            timestamp = datetime.now(timezone.utc)
            logger.debug("Timestamp for line: %s", timestamp)
            keys = meta_csi_data_index
            values = line.split(',') + [timestamp]
            data_dict = {k: v for k, v in zip(keys, values)}
            logger.debug("Parsed data dictionary: %s", data_dict)
            csi_data_list = self.get_csi_data_list(data_dict['csi_data'])
            if csi_data_list:
                data_dict['csi_data'] = csi_data_list
                logger.debug("CSI data list: type: %s, length: %d, data: %s", type(csi_data_list), len(csi_data_list), csi_data_list)
                return MetaCsiData.model_validate(data_dict)
            logger.debug("Failed to extract CSI data list from line: %s", line)
            return None
        else:
            self._handle_no_data(last_data_time)

        logger.debug("No valid line found.")
        return None

    def get_csi_data_list(self, csi_data_str, expected_length=128):
        try:
            # データ文字列をリスト化し、長さをチェック
            csi_data_list = list(map(int, csi_data_str.strip("[]").split()))
            if len(csi_data_list) == expected_length:
                logger.debug("CSI data list length matches expected: %d", expected_length)
                return csi_data_list
            else:
                logger.debug("CSI data list length mismatch: expected %d, got %d, csi_data_list: %s", expected_length, len(csi_data_list), csi_data_list)
                return []
        except ValueError as e:
            # データ変換中にエラーが発生した場合は空リストを返す
            logger.debug("Error parsing CSI data: %s", e)
            return []

    def is_valid_line(self, line):
        LINE_PATTERN = re.compile(r"([A-Z0-9._\-[\]:\s]+,){25}")
        if line:
            is_valid = LINE_PATTERN.match(line) is not None
            logger.debug("Line validation result: %s for line: %s", is_valid, line)
            return is_valid
        logger.debug("No line to validate.")
        return False

class SerialReaderManager:
    def __init__(self, config):
        self.serial_connection = None
        self.config = config

    def __enter__(self) -> 'SerialReaderManager':
        self.connect()
        return self

    def connect(self):
        try:
            self.serial_connection = serial.Serial(
                self.config.serial_port,
                self.config.baud_rate,
                timeout=self.config.timeout
            )
            logger.info("Connected to %s at baud rate %d", self.config.serial_port, self.config.baud_rate)
        except serial.SerialException as e:
            logger.error("Failed to connect to serial port: %s", e)
            raise

    def reconnect(self):
        if self.serial_connection:
            self.serial_connection.close()
            logger.info("Serial connection closed for reconnection.")
        time.sleep(self.config.reconnect_delay)  # 一旦スリープ
        self.connect()  # 再接続を試みる

    def get_reader(self) -> SerialReader:
        if self.serial_connection is None:
            logger.error("Attempted to get reader without an active serial connection.")
            raise RuntimeError('Serial is not connected.')
        logger.debug("Serial connection established, returning SerialReader.")
        return SerialReader(self.serial_connection, self.config.no_data_timeout, NO_DATA_SLEEP_DURATION)
    
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.serial_connection is not None:
            self.serial_connection.close()
            logger.info("Serial connection closed.")