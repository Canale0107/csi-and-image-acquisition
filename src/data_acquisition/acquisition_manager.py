import time
import logging
from pathlib import Path
from typing import List
import threading
import traceback
from contextlib import ExitStack

from src.config import DataAcquisitionConfig, CameraConfig, InfluxDBConfig
from src.camera import MetaCameraManager, MetaFrame
from src.utils.file_manager import FilePathManager
from src.writers import DataWriter, WriterManager, CSVWriterManager, InfluxDBWriterManager


logger = logging.getLogger(__name__)


class DataAcquisitionManager:
    def __init__(self, config: DataAcquisitionConfig, session_id: str,
                meta_camera_manager: MetaCameraManager,
                filepath_manager: FilePathManager,
                writer_managers: List[WriterManager], stop_event: threading.Event) -> None:
        self.config = config
        self.session_id = session_id
        self.meta_camera_manager = meta_camera_manager
        self.filepath_manager = filepath_manager
        self.writer_managers = writer_managers
        self.stop_event = stop_event

    def save_meta_data(self, meta_frame: MetaFrame,
                             data_writers: List[DataWriter]) -> None:
        """ イメージを保存し、データを書き込む """
        for data_writer in data_writers:
            try:
                data_writer.write_data(meta_frame.meta_data)
            except Exception as e:
                logger.error("Failed to write data: %s", e)
                traceback.print_exc()  # エラーメッセージを表示
                raise  # エラーを再度発生させてプログラムを停止させる

    def start_acquisition(self) -> None:
        """ データ取得の開始 """
        with ExitStack() as stack:
            meta_camera = stack.enter_context(self.meta_camera_manager).get_reader()
            data_writers = [stack.enter_context(wm).get_writer() for wm in self.writer_managers]

            # カメラのFPSに基づいてスリープ時間を計算 (秒)
            fps = self.meta_camera_manager.fps
            sleep_time = 1.0 / fps  # 1フレームの取得に要する時間 (秒)
            next_frame_time = time.time() + sleep_time  # 最初のフレーム取得時間を設定

            try:
                while not self.stop_event.is_set():
                    try:
                        meta_frame = meta_camera.read_meta_frame()
                        meta_frame.save_frame(self.filepath_manager.image_dirpath)
                        self.save_meta_data(meta_frame, data_writers)

                        # 次のフレーム取得までの時間を計算し、必要ならスリープ
                        time.sleep(max(0, next_frame_time - time.time()))  # スリープ時間が負でないか確認
                        next_frame_time += sleep_time  # 次のフレーム取得時間を更新

                    except Exception as e:
                        logger.error("Error during acquisition: %s", e)
                        break  # エラー時にループを抜ける

            finally:
                logger.info("Acquisition stopped.")


# TODO: InfluxDBはカメラごとではなく、共通で1つでいいのでは
def initialize_managers(influxdb_config: InfluxDBConfig,
                        filepath_manager: FilePathManager):
    try:
        csv_writer_manager = CSVWriterManager(filepath_manager)
        influxdb_writer_manager = InfluxDBWriterManager(influxdb_config)
        return csv_writer_manager, influxdb_writer_manager
    except Exception as e:
        logger.error("Initialization failed: %e", e)
        raise


def get_writer_managers(data_acquisition_config: DataAcquisitionConfig, 
                      csv_writer_manager: WriterManager,
                      influxdb_writer_manager: WriterManager) -> List[WriterManager]:
    return [
        manager for manager, enabled in zip(
            [csv_writer_manager, influxdb_writer_manager],
            [data_acquisition_config.save_to_csv, data_acquisition_config.send_to_db]
        )
        if enabled
    ]

def run_acquisition_for_camera(camera_config: CameraConfig,
                               data_acquisition_config: DataAcquisitionConfig,
                               influxdb_config: InfluxDBConfig,
                               session_id: str, stop_event: threading.Event) -> None:
    """ カメラごとにデータ取得を行う """

    image_dirpath = (
        Path(data_acquisition_config.data_dirpath)
        / session_id
        / f'camera{camera_config.camera_index}'
    )

    csv_filepath = (
        Path(data_acquisition_config.data_dirpath)
        / session_id
        / f'camera{camera_config.camera_index}'
        / 'meta_data.csv'
    )

    filepath_manager = FilePathManager(image_dirpath, csv_filepath)

    # マネージャーの初期化
    csv_writer_manager, influxdb_writer_manager = initialize_managers(influxdb_config, filepath_manager)

    meta_camera_manager = MetaCameraManager(
        data_acquisition_config,
        camera_config,
        session_id,
        filepath_manager
    )

    # データマネージャーの設定
    writer_managers = get_writer_managers(data_acquisition_config, csv_writer_manager, influxdb_writer_manager)

    data_acquisition_manager = DataAcquisitionManager(
        data_acquisition_config,
        session_id,
        meta_camera_manager,
        filepath_manager,
        writer_managers, stop_event
    )

    try:
        data_acquisition_manager.start_acquisition()
    except Exception as e:
        logger.error("Acquisition error for camera %d: %s", camera_config.camera_index, e)
        raise
