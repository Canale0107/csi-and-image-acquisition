import os
import csv
import time
import logging
from pathlib import Path
from typing import Tuple, List
from datetime import datetime, timezone
from contextlib import ExitStack
import traceback
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

    def __init__(self, camera_config, acquisition_datetime):
        self.camera_config = camera_config
        self.acquisition_datetime = acquisition_datetime
        self.resolution = f'{self.camera_config.width}x{self.camera_config.height}'
        self.filepath = self._get_filepath()

    def _get_parent_dir(self):
        """親ディレクトリを取得する（例：日付を親ディレクトリとする）"""
        date = self.acquisition_datetime.strftime("%Y-%m-%d")
        hour = self.acquisition_datetime.strftime("%H")
        minute = self.acquisition_datetime.strftime("%M")
        second = self.acquisition_datetime.strftime("%S")
        parent_dir = Path('camera' + str(self.camera_config.camera_index)) / date / hour / minute / second
        return parent_dir

    def _get_filepath(self):
        # 親ディレクトリを取得
        parent_dir = self._get_parent_dir()
        
        # 現在の秒を取得
        current_second = self.acquisition_datetime.strftime("%S")
        
        # 秒が変わったら連番をリセット
        if ImageMetaData.current_second != current_second:
            ImageMetaData.image_counter = 0  # 連番をリセット
            ImageMetaData.current_second = current_second  # 秒を更新
        else:
            ImageMetaData.image_counter += 1  # 連番をインクリメント

        # ファイル名を連番付きで生成
        filename = (f'camera{self.camera_config.camera_index}_'
                    f'{self.acquisition_datetime.strftime("%Y-%m-%d_%H-%M-%S")}_'
                    f'{ImageMetaData.image_counter}.jpg')

        filepath = os.path.join(parent_dir, filename)
        return filepath


class Image():
    def __init__(self, frame: np.ndarray, meta_data: ImageMetaData):
        self.frame = frame
        self.meta_data = meta_data
    def save(self, image_save_dirpath):
        filepath = os.path.join(image_save_dirpath, self.meta_data.filepath)
        # ディレクトリが存在しない場合は作成する
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cv2.imwrite(filepath, self.frame)
        logger.info(f"Image saved: {filepath}")


class CameraManager():
    """
    カメラの管理を行う
    """
    def __init__(self, config: CameraConfig):
        self.cap = None
        self.config = config

    def __enter__(self):

        self.cap = cv2.VideoCapture(self.config.camera_index)

        # 解像度を指定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)

        # FPSを指定
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not self.cap.isOpened():
            raise ValueError(f"Camera {self.config.camera_index} cannot be opened.")
        return self
    
    def get_image(self) -> Tuple[bool, Image]:
        try:
            ret, frame = self.cap.read()
            if not ret:
                raise RuntimeError("Failed to capture frame from camera.")
            
            acquisition_datetime = datetime.now(timezone.utc)
            meta_data = ImageMetaData(self.config, acquisition_datetime)

            frame = cv2.flip(frame, 1)
            image = Image(frame, meta_data)

            return ret, image
        except Exception as e:
            logger.error("Error capturing image: %s", e)
            raise  # エラーを上位に投げる

    def __exit__(self, exc_type, exc_value, traceback):
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()


class CSVManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.fieldnames = ['filepath', 'timestamp']
        self.file = None
        self.writer = None

    def __enter__(self):
        """ データ取得開始時にファイルを開いてCSV writerを初期化 """
        # ディレクトリが存在しない場合は作成する
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.file = open(self.filepath, mode='w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames)
        self.writer.writeheader()
        return self

    def write_data(self, image):
        """ 画像のメタデータをCSVファイルに書き込む """
        if self.writer:
            try:
                filepath = image.meta_data.filepath
                timestamp = image.meta_data.acquisition_datetime.timestamp()
                data = {'filepath': filepath, 'timestamp': timestamp}
                self.writer.writerow(data)
                logger.info('metadata written: %s', data)
            except Exception as e:
                logger.error("Error occured while writing to CSV: %s", e)
                raise

    def __exit__(self, exc_type, exc_value, traceback):
        """ データ取得終了時にファイルを閉じる """
        if self.file:
            self.file.close()


class DBConfig(BaseModel):
    url: str
    token: str
    org: str
    bucket: str

    def get_client(self):
        """
        InfluxDBClientを取得するメソッド。
        """
        return InfluxDBClient(url=self.url, token=self.token, org=self.org)

class DBManager:
    def __init__(self, config: DBConfig, session_id):
        self.config = config
        self.session_id = session_id
        self.client = None
        self.write_api = None

    def __enter__(self):
        """ データ取得開始時にデータベースに接続 """
        self.client = self.config.get_client()
        self.write_api = self.client.write_api()

        # データベース接続のテスト
        try:
            health = self.client.health()
            logger.info(f"Database health: {health.status}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

        return self

    def write_data(self, image):
        """ 画像データのメタ情報をデータベースに書き込む """
        try:
            measurement = "IMAGE_DATA"
            fields = {"filepath": image.meta_data.filepath}
            tags = {"session_id": self.session_id,
                    "camera_index": image.meta_data.camera_config.camera_index}
            timestamp = image.meta_data.acquisition_datetime

            point = Point(measurement).tag("session_id", tags["session_id"]) \
                                        .tag("camera_index", tags["camera_index"]) \
                                        .field("filepath", fields["filepath"]) \
                                        .time(timestamp, WritePrecision.NS)
            self.write_api.write(bucket=self.config.bucket, record=point)
            logger.info(f"Data written to DB: {point}")
        except Exception as e:
            logger.error("Error occured while writing data to DB: %s", e)
            raise

    def __exit__(self, exc_type, exc_value, traceback):
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
                camera_manager: CameraManager, db_manager: DBManager, csv_manager: CSVManager):
        self.config = config
        self.session_id = session_id
        self.camera_manager = camera_manager
        self.db_manager = db_manager
        self.csv_manager = csv_manager
        self._running = False

    def stop_acquisition(self):
        self._running = False

    def start_acquisition(self):
        """ データ取得の開始 """

        image_save_dirpath = os.path.join(self.config.data_dirpath, self.session_id, 'image')

        with ExitStack() as stack:
            camera_manager = stack.enter_context(self.camera_manager)
            csv_manager = stack.enter_context(self.csv_manager)
            db_manager = stack.enter_context(self.db_manager)
            # カメラのFPSに基づいてスリープ時間を計算 (秒)
            fps = self.camera_manager.config.fps
            sleep_time = 1.0 / fps  # 1フレームの取得に要する時間 (秒)
            next_frame_time = time.time() + sleep_time  # 最初のフレーム取得時間を設定

            self._running = True
            try:
                while self._running:
                    ret, image = camera_manager.get_image()
                    if not ret:
                        logger.error(f"Error capturing frame from camera {camera_manager.config.camera_index}")
                        break

                    image.save(image_save_dirpath)
                    if self.config.save_to_csv:
                        csv_manager.write_data(image)
                    if self.config.send_to_db:
                        db_manager.write_data(image)

                    # 次のフレーム取得までの時間を計算し、必要ならスリープ
                    time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                    next_frame_time += sleep_time  # 次のフレーム取得時間を更新
            except Exception as e:
                logger.error(f"Error during acquisition: {e}")
                raise  # エラーを再度上位層に投げる
            finally:
                self.stop_acquisition()


def load_configs():
    try:
        with open("config.yml", "r", encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        data_acquisition_config = DataAcquisitionConfig.parse_obj(config['data_acquisition'])
        camera_config = CameraConfig.parse_obj(config['camera'])
        db_config = DBConfig.parse_obj(config['db'])

    except FileNotFoundError as e:
        logger.error("Configuration file not found.")
        raise

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        raise
    
    except ValidationError as e:
        logger.error(f"Configuration validation error: {e}")
        raise

    return data_acquisition_config, camera_config, db_config


def main():
    try:
        config, camera_config, db_config = load_configs()
    except Exception as e:
        logger.error("Failed to load configs: %s", e)
        return

    session_id = 'session_' + datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filepath = Path(config.data_dirpath) / session_id / 'meta_data.csv'

    try:
        camera_manager = CameraManager(camera_config)
        db_manager = DBManager(db_config, session_id)
        csv_manager = CSVManager(csv_filepath)
    except Exception as e:
        logger.error("Initialization failed: %s", e)
        raise

    data_acquisition_manager = DataAcquisitionManager(config, session_id, camera_manager, db_manager, csv_manager)

    try:
        data_acquisition_manager.start_acquisition()
    except KeyboardInterrupt:
        logger.info("Shutting down data acquisition.")
        data_acquisition_manager.stop_acquisition()
    except Exception as e:
        logger.error(f"Acquisition error: {e}")
        raise

if __name__ == "__main__":
    main()
