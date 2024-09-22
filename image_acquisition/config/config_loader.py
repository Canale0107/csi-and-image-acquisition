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


def load_configs(config_path: str) -> Tuple[DataAcquisitionConfig, CameraConfig, InfluxDBConfig]:
    try:
        logger.info("Loading configuration file: config.yml")
        with open(config_path, "r", encoding='utf-8') as file:
            config = yaml.safe_load(file)

        logger.info("Parsing data acquisition configuration.")
        image_acquisition_config = DataAcquisitionConfig.parse_obj(config['image_acquisition'])
        logger.info("Data acquisition config: %s", image_acquisition_config.dict())

        logger.info("Parsing camera configurations.")
        camera_configs = [CameraConfig.parse_obj(cam_config) for cam_config in config['camera']]
        cam_config_dicts =  [cam_config.dict() for cam_config in camera_configs]
        logger.info("Loaded %d camera configurations: %s", len(camera_configs), cam_config_dicts)

        logger.info("Parsing InfluxDB configuration.")
        influxdb_config = InfluxDBConfig.parse_obj(config['influxdb'])
        logger.info("InfluxDB configuration loaded (token is hidden for security reasons).")
        influxdb_config_dict = influxdb_config.dict(exclude={'token'})
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

    return {
        'image_acquisition': image_acquisition_config,
        'cameras': camera_configs,
        'writers': {
            'influxdb': influxdb_config
        }
    }
