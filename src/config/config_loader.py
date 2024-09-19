import yaml
from typing import Tuple
import logging

from pydantic import BaseModel, ValidationError
from influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


class DataAcquisitionConfig(BaseModel):
    data_dirpath: str
    save_to_csv: bool
    send_to_db: bool


class CameraConfig(BaseModel):
    camera_index: int
    width: int
    height: int
    fps: int


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


def load_configs() -> Tuple[DataAcquisitionConfig, CameraConfig, InfluxDBConfig]:
    try:
        with open("config.yml", "r", encoding='utf-8') as file:
            config = yaml.safe_load(file)

        data_acquisition_config = DataAcquisitionConfig.parse_obj(config['data_acquisition'])
        camera_configs = [CameraConfig.parse_obj(cam_config) for cam_config in config['camera']]
        db_config = InfluxDBConfig.parse_obj(config['db'])

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        raise

    except yaml.YAMLError as e:
        logger.error("Error parsing YAML file: %s", e)
        raise

    except ValidationError as e:
        logger.error("Configuration validation error: %s", e)
        raise

    return data_acquisition_config, camera_configs, db_config