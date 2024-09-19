import os
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


class ImageMetaData():
    image_counter = 0  # クラス変数で連番を管理
    current_second = None  # 現在の秒を保持

    def __init__(self, session_id: str, camera_index: int, timestamp: datetime) -> None:
        self.session_id = session_id
        self.camera_index = camera_index
        self.timestamp = timestamp
        self.filepath = self._get_filepath()

    def to_dict(self):
        return {
            "session_id": str(self.session_id),
            "camera_index": int(self.camera_index),
            "filepath": str(self.filepath), 
            "timestamp": self.timestamp
        }

    def _get_parent_dir(self) -> Path:
        """親ディレクトリを取得する（例：日付を親ディレクトリとする）"""
        date = self.timestamp.strftime("%Y-%m-%d")
        hour = self.timestamp.strftime("%H")
        minute = self.timestamp.strftime("%M")
        second = self.timestamp.strftime("%S")
        parent_dir = Path(self.session_id) / 'image' / ('camera' + str(self.camera_index)) / date / hour / minute / second
        return parent_dir

    def _get_filepath(self) -> Path:
        # 親ディレクトリを取得
        parent_dir = self._get_parent_dir()

        # 現在の秒を取得
        current_second = self.timestamp.strftime("%S")

        # 秒が変わったら連番をリセット
        if ImageMetaData.current_second != current_second:
            ImageMetaData.image_counter = 0  # 連番をリセット
            ImageMetaData.current_second = current_second  # 秒を更新
        else:
            ImageMetaData.image_counter += 1  # 連番をインクリメント

        # ファイル名を連番付きで生成
        filename = (f'camera{self.camera_index}_'
                    f'{self.timestamp.strftime("%Y-%m-%d_%H-%M-%S")}_'
                    f'{ImageMetaData.image_counter}.jpg')

        filepath = Path(parent_dir) / filename
        return filepath


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
    def write_data(self, data: Any) -> None:
        """データを適切な書き込み先に保存する抽象メソッド"""
        pass


class DataManager(ABC):
    @abstractmethod
    def get_writer(self) -> DataWriter:
        pass


class CSVWriter(DataWriter):
    def __init__(self, file) -> None:
        self.writer = csv.DictWriter(file, fieldnames=['session_id', 'camera_index', 'filepath', 'timestamp'])
        self.writer.writeheader()

    def write_data(self, data: dict) -> None:
        """ CSVにデータを書き込む """
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].timestamp()
        self.writer.writerow(data)
        logger.info("Data written to CSV: %s", data)


class CSVManager(DataManager):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.file = None
        self.writer = None

    def __enter__(self) -> 'CSVManager':
        """ 一度だけCSVファイルをオープン """
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.file = open(self.filepath, mode='w', newline='', encoding='utf-8')
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

    def write_data(self, data: dict) -> None:
        """ InfluxDBにデータを書き込む """

        assert isinstance(data.get('timestamp'), datetime), \
            f"Expected timestamp to be datetime, but got {type(data.get('timestamp'))}"

        point = Point("IMAGE_DATA").tag("session_id", data["session_id"]) \
                                    .tag("camera_index", data["camera_index"]) \
                                    .field("filepath", data["filepath"]) \
                                    .time(data["timestamp"], WritePrecision.NS)
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
                camera_manager: CameraManager) -> None:
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self._running = False

    def stop_acquisition(self) -> None:
        self._running = False

    def start_acquisition(self, data_managers: List[DataManager]) -> None:
        """ データ取得の開始 """

        image_save_dirpath = os.path.join(self.config.data_dirpath)

        with ExitStack() as stack:
            camera_manager = stack.enter_context(self.camera_manager)

            writers = []
            for data_manager in data_managers:
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

                    meta_data = ImageMetaData(
                        self.session_id, 
                        self.camera_manager.config.camera_index,
                        timestamp)
                    image = Image(frame, meta_data)

                    image.save(image_save_dirpath)

                    for writer in writers:
                        writer.write_data(meta_data.to_dict())

                    # 次のフレーム取得までの時間を計算し、必要ならスリープ
                    time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                    next_frame_time += sleep_time  # 次のフレーム取得時間を更新

            except Exception as e:
                logger.error("Error during acquisition: %s", e)
                raise  # エラーを再度上位層に投げる

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
        config, camera_config, db_config = load_configs()

    except Exception as e:
        logger.error("Failed to load configs: %s", e)
        return

    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filepath = Path(config.data_dirpath) / session_id / 'meta_data.csv'

    try:
        camera_manager = CameraManager(camera_config)
        csv_manager = CSVManager(csv_filepath)
        db_manager = DBManager(db_config, session_id)

    except Exception as e:
        logger.error("Initialization failed: %s", e)
        raise

    data_acquisition_manager = DataAcquisitionManager(config, session_id, camera_manager)

    try:
        data_managers = []

        if config.save_to_csv:
            data_managers.append(csv_manager)

        if config.send_to_db:
            data_managers.append(db_manager)

        data_acquisition_manager.start_acquisition(data_managers)

    except KeyboardInterrupt:
        logger.info("Shutting down data acquisition.")
        data_acquisition_manager.stop_acquisition()

    except Exception as e:
        logger.error("Acquisition error: %s", e)
        raise

if __name__ == "__main__":
    main()
