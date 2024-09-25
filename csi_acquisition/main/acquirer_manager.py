import logging

logger = logging.getLogger(__name__)

class CsiAcquirer:
    def __init__(self, serial_reader, data_writers):
        self.serial_reader = serial_reader
        self.data_writers = data_writers

    def acquirer_meta_csi_data(self, last_data_time):
        try:
            meta_csi_data = self.serial_reader.read_meta_csi_data(last_data_time)
        except TimeoutError as e:
            logger.error("Timeout while reading CSI data: %s", e)
            raise e

        if meta_csi_data:
            all_success = True
            for data_writer in self.data_writers:
                try:
                    data_writer.write_data(meta_csi_data)
                except Exception as e:
                    logger.error("Failed to write data: %s", e)
                    all_success = False
                    # continue  # 他の data_writer の処理を続けたい場合
                    raise  # 一つの失敗で停止したい場合はこちら
            return all_success  # 全て成功したかどうかを返す
        else:
            return False

class CsiAcquirerManager:
    def __init__(self, session_id,
                 serial_reader_manager,
                 writer_managers):
        self.session_id = session_id
        self.serial_reader_manager = serial_reader_manager
        self.serial_reader = None
        self.writer_managers = writer_managers
        self.writers = []

    def __enter__(self):
        self.serial_reader = self.serial_reader_manager.__enter__().get_reader()
        self.writers = [wm.__enter__().get_writer() for wm in self.writer_managers]
        return self
    
    def get_acquirer(self) -> CsiAcquirer:
        if self.serial_reader is None:
            raise RuntimeError("SerialReader is not ready.")
        if self.writers is []:
            raise RuntimeError("DataWriters is not ready.")
        return CsiAcquirer(self.serial_reader, self.writers)
    
    def __exit__(self, exc_type, exc_value, traceback):

        # リソースの解放やログの処理
        logger.info("Releasing resources and stopping acquisition.")
        self.serial_reader_manager.__exit__(exc_type, exc_value, traceback)
        for writer_manager in self.writer_managers:
            writer_manager.__exit__(exc_type, exc_value, traceback)

        if exc_type:
            logger.error("An exception occurred: %s", exc_value)
