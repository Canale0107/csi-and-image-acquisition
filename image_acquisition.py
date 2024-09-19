import os
import io
import csv
import time
import logging
from pathlib import Path
from typing import Tuple, List, Any
from datetime import datetime, timezone
from contextlib import ExitStack
from abc import ABC, abstractmethod
import yaml
from pydantic import BaseModel, ValidationError
import numpy as np
import cv2
from influxdb_client import InfluxDBClient, Point, WritePrecision


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


class CameraConfig(BaseModel):
    camera_index: int
    width: int
    height: int
    fps: int


class FilePathManager():

    def __init__(self, session_id: str, camera_index: int) -> None:
        self.session_id = session_id
        self.camera_index = camera_index
        self.image_counter = 0
        self.current_second = None

    def _get_parent_dir(self, timestamp) -> Path:
        """親ディレクトリを取得する（例：日付を親ディレクトリとする）"""
        date = timestamp.strftime("%Y-%m-%d")
        hour = timestamp.strftime("%H")
        minute = timestamp.strftime("%M")
        parent_dir = Path(self.session_id) / 'image' / ('camera' + str(self.camera_index)) / date / hour / minute
        return parent_dir

    def get_filepath(self, timestamp) -> Path:
        # 親ディレクトリを取得
        parent_dir = self._get_parent_dir(timestamp)

        # 現在の秒を取得
        current_second = timestamp.strftime("%S")

        # 秒が変わったら連番をリセット
        if self.current_second != current_second:
            self.image_counter = 0  # 連番をリセット
            self.current_second = current_second  # 秒を更新
        else:
            self.image_counter += 1  # 連番をインクリメント

        # ファイル名を連番付きで生成
        filename = (f'camera{self.camera_index}_'
                    f'{timestamp.strftime("%Y-%m-%d_%H-%M-%S")}_'
                    f'{self.image_counter}.jpg')

        filepath = Path(parent_dir) / filename
        return filepath


class ImageMetaData(BaseModel):
    session_id: str
    camera_index: int
    timestamp: datetime
    filepath: Path


class Image():
    def __init__(self, frame: np.ndarray, meta_data: ImageMetaData) -> None:
        self.frame = frame
        self.meta_data = meta_data

    def save(self, image_save_dirpath: Path) -> None:
        filepath = Path(image_save_dirpath) / self.meta_data.filepath
        # ディレクトリが存在しない場合は作成する
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cv2.imwrite(filepath, self.frame)
        logger.info("Image saved: %s", filepath)


class CameraManager():
    """
    カメラの管理を行う
    """
    def __init__(self, config: CameraConfig) -> None:
        self.cap = None
        self.config = config

    def __enter__(self) -> 'CameraManager':

        self.cap = cv2.VideoCapture(self.config.camera_index)

        # 解像度を指定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)

        # FPSを指定
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not self.cap.isOpened():
            raise ValueError(f"Camera {self.config.camera_index} cannot be opened.")
        return self

    def get_frame(self) -> Tuple[bool, Image]:
        try:
            ret, frame = self.cap.read()
            if not ret:
                raise RuntimeError("Failed to capture frame from camera.")

            frame = cv2.flip(frame, 1)

            return ret, frame

        except Exception as e:
            logger.error("Error capturing image: %s", e)
            raise 

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()


class DataWriter(ABC):
    @abstractmethod
    def write_data(self, meta_data: Any) -> None:
        """メタデータを適切な書き込み先に保存する抽象メソッド"""
        pass


class DataManager(ABC):
    @abstractmethod
    def get_writer(self) -> DataWriter:
        pass


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


class DBConfig(BaseModel):
    url: str
    token: str
    org: str
    bucket: str

    def get_client(self) -> InfluxDBClient:
        """
        InfluxDBClientを取得するメソッド。
        """
        return InfluxDBClient(url=self.url, token=self.token, org=self.org)


class InfluxDBWriter(DataWriter):
    def __init__(self, write_api, bucket: str) -> None:
        self.write_api = write_api
        self.bucket = bucket

    def write_data(self, meta_data: ImageMetaData) -> None:
        """ InfluxDBにデータを書き込む """

        assert isinstance(meta_data.timestamp, datetime), \
            f"Expected timestamp to be datetime, but got {type(meta_data.get('timestamp'))}"

        point = (Point("IMAGE_DATA").tag("session_id", str(meta_data.session_id))
                                    .tag("camera_index", int(meta_data.camera_index))
                                    .field("filepath", str(meta_data.filepath))
                                    .time(meta_data.timestamp, WritePrecision.NS)
        )
        self.write_api.write(bucket=self.bucket, record=point)
        logger.info("Data written to DB: %s", point)


class DBManager(DataManager):
    def __init__(self, config: DBConfig, session_id: str) -> None:
        self.config = config
        self.session_id = session_id
        self.client = None
        self.write_api = None

    def __enter__(self) -> 'DBManager':
        """ データ取得開始時にデータベースに接続 """
        self.client = self.config.get_client()
        self.write_api = self.client.write_api()

        # データベース接続のテスト
        try:
            health = self.client.health()
            logger.info("Database health: %s", health.status)
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


class DataAcquisitionConfig(BaseModel):
    data_dirpath: str
    save_to_csv: bool
    send_to_db: bool


class DataAcquisitionManager():
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
                camera_manager: CameraManager, filepath_manager: FilePathManager,
                data_managers: List[DataManager]) -> None:
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self.filepath_manager = filepath_manager
        self.data_managers = data_managers
        self._running = False

    def stop_acquisition(self) -> None:
        self._running = False

    def start_acquisition(self) -> None:
        """ データ取得の開始 """

        image_save_dirpath = os.path.join(self.config.data_dirpath)

        with ExitStack() as stack:
            camera_manager = stack.enter_context(self.camera_manager)

            writers = []
            for data_manager in self.data_managers:
                data_manager = stack.enter_context(data_manager)
                writer = data_manager.get_writer()
                writers.append(writer)

            # カメラのFPSに基づいてスリープ時間を計算 (秒)
            fps = self.camera_manager.config.fps
            sleep_time = 1.0 / fps  # 1フレームの取得に要する時間 (秒)
            next_frame_time = time.time() + sleep_time  # 最初のフレーム取得時間を設定

            try:
                self._running = True
                while self._running:

                    ret, frame = camera_manager.get_frame()
                    if not ret:
                        logger.error("Error capturing frame from camera %d", camera_manager.config.camera_index)
                        break

                    timestamp = datetime.now(timezone.utc)

                    filepath = self.filepath_manager.get_filepath(timestamp)
                    meta_data = ImageMetaData(
                        session_id = self.session_id,
                        camera_index = self.camera_manager.config.camera_index,
                        timestamp = timestamp,
                        filepath = filepath)
                    image = Image(frame, meta_data)

                    image.save(image_save_dirpath)

                    for writer in writers:
                        try:
                            writer.write_data(meta_data)
                        except Exception as e:
                            logger.error("Failed to write data: %s", e)

                    # 次のフレーム取得までの時間を計算し、必要ならスリープ
                    time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                    next_frame_time += sleep_time  # 次のフレーム取得時間を更新

            except Exception as e:
                logger.error("Error during acquisition: %s", e)
                self.stop_acquisition()

            finally:
                self.stop_acquisition()


def load_configs() -> Tuple[DataAcquisitionConfig, CameraConfig, DBConfig]:
    try:
        with open("config.yml", "r", encoding='utf-8') as file:
            config = yaml.safe_load(file)

        data_acquisition_config = DataAcquisitionConfig.parse_obj(config['data_acquisition'])
        camera_config = CameraConfig.parse_obj(config['camera'])
        db_config = DBConfig.parse_obj(config['db'])

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        raise

    except yaml.YAMLError as e:
        logger.error("Error parsing YAML file: %s", e)
        raise

    except ValidationError as e:
        logger.error("Configuration validation error: %s", e)
        raise

    return data_acquisition_config, camera_config, db_config


def main() -> None:
    try:
        data_acquisition_config, camera_config, db_config = load_configs()

    except Exception as e:
        logger.error("Failed to load configs: %s", e)
        return

    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filepath = Path(data_acquisition_config.data_dirpath) / session_id / 'meta_data.csv'

    try:
        camera_manager = CameraManager(camera_config)
        csv_manager = CSVManager(csv_filepath)
        db_manager = DBManager(db_config, session_id)
        filepath_manager = FilePathManager(session_id, camera_config.camera_index)

    except Exception as e:
        logger.error("Initialization failed: %s", e)
        raise

    data_managers = []

    if data_acquisition_config.save_to_csv:
        data_managers.append(csv_manager)

    if data_acquisition_config.send_to_db:
        data_managers.append(db_manager)

    data_acquisition_manager = DataAcquisitionManager(data_acquisition_config, session_id, camera_manager, filepath_manager, data_managers)

    try:
        data_acquisition_manager.start_acquisition()

    except KeyboardInterrupt:
        logger.info("Shutting down data acquisition.")
        data_acquisition_manager.stop_acquisition()

    except Exception as e:
        logger.error("Acquisition error: %s", e)
        raise

if __name__ == "__main__":
    main()
