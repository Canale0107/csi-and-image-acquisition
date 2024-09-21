from pathlib import Path


class FilePathManager:
    def __init__(self, image_dirpath: Path, csv_filepath: Path) -> None:
        self.image_dirpath = image_dirpath
        self.csv_filepath = csv_filepath
        self.frame_counter = 0
        self.current_second = None

    def _get_frame_parent_dir(self, timestamp) -> Path:
        """親ディレクトリを取得する（例：日付を親ディレクトリとする）"""
        date = timestamp.strftime("%Y-%m-%d")
        hour = timestamp.strftime("%H")
        minute = timestamp.strftime("%M")
        parent_dir = Path(date) / hour / minute
        return parent_dir

    def get_frame_filepath(self, timestamp) -> Path:
        # 親ディレクトリを取得
        parent_dir = self._get_frame_parent_dir(timestamp)

        # 現在の秒を取得
        current_second = timestamp.strftime("%S")

        # 秒が変わったら連番をリセット
        if self.current_second != current_second:
            self.frame_counter = 0  # 連番をリセット
            self.current_second = current_second  # 秒を更新
        else:
            self.frame_counter += 1  # 連番をインクリメント

        # ファイル名を連番付きで生成
        filename = (f'{timestamp.strftime("%Y-%m-%d_%H-%M-%S")}_'
                    f'{self.frame_counter}.jpg')

        filepath = Path(parent_dir) / filename
        return filepath
