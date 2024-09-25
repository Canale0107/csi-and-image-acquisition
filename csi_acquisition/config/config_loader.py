import yaml
import logging
from typing import List, Dict, Union

from pydantic import BaseModel, ValidationError
from influxdb_client import InfluxDBClient


logger = logging.getLogger(__name__)


class CsiAcquisitionConfig(BaseModel):
    data_dirpath: str
    save_to_csv: bool
    send_to_db: bool
    send_via_udp: bool


class CsiConfig(BaseModel):
    serial_port: str
    baud_rate: int
    timeout: float
    no_data_timeout: float


class UdpConfig(BaseModel):
    receiver_ips_ports: List[Dict[str, Union[str, int]]]


class InfluxDBConfig(BaseModel):
    url: str
    token: str
    org: str
    bucket: str

    def get_client(self) -> InfluxDBClient:
        """
        InfluxDBClientを取得するメソッド。
        """
        return InfluxDBClient(url=self.url, token=self.token, org=self.org)


class Config(BaseModel):
    csi_acquisition: CsiAcquisitionConfig
    csi: CsiConfig
    udp: UdpConfig
    influxdb: InfluxDBConfig


def load_configs(config_path: str) -> Config:
    try:
        logger.info("Loading configuration file: config.yml")
        with open(config_path, "r", encoding='utf-8') as file:
            config = yaml.safe_load(file)

        logger.info("Parsing csi acquisition configuration.")
        csi_acquisition_config = CsiAcquisitionConfig.model_validate(config['csi_acquisition'])
        logger.info("Csi acquisition config: %s", csi_acquisition_config.model_dump())

        logger.info("Parsing CSI configurations.")
        csi_config = CsiConfig.model_validate(config['csi'])
        logger.info("Loaded CSI configurations: %s", csi_config.model_dump())

        logger.info("Parsing UDP configurations.")
        udp_config = UdpConfig.model_validate(config['udp'])
        print(udp_config)
        logger.info("Loaded UDP configurations: %s", udp_config.model_dump())

        logger.info("Parsing InfluxDB configuration.")
        influxdb_config = InfluxDBConfig.model_validate(config['influxdb'])
        logger.info("InfluxDB configuration loaded (token is hidden for security reasons).")
        influxdb_config_dict = influxdb_config.model_dump(exclude={'token'})
        logger.info("InfluxDB config (excluding token): %s", influxdb_config_dict)

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        raise

    except yaml.YAMLError as e:
        logger.error("Error parsing YAML file: %s", e)
        raise

    except ValidationError as e:
        logger.error("Configuration validation error: %s", e)
        raise

    return Config(
        csi_acquisition = csi_acquisition_config,
        csi = csi_config,
        udp = udp_config,
        influxdb = influxdb_config
    )
