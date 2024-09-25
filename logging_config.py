import os
from pathlib import Path
import logging
from colorama import Fore, Style, init

# 初期化 (Windows 対応)
init(autoreset=True)

# カスタムフォーマッター
class ColoredImageFormatter(logging.Formatter):
    FORMATS = {
        'asctime': Fore.CYAN,
        'name': Fore.MAGENTA,
        'levelname': Fore.YELLOW,
        'message': Fore.WHITE
    }

    LOG_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        log_color = self.LOG_COLORS.get(record.levelno, Fore.WHITE)
        record.asctime = f"{self.FORMATS['asctime']}{self.formatTime(record, self.datefmt)}{Style.RESET_ALL}"
        record.name = f"{self.FORMATS['name']}{record.name}{Style.RESET_ALL}"
        record.levelname = f"{self.FORMATS['levelname']}{record.levelname}{Style.RESET_ALL}"
        record.message = f"{self.FORMATS['message']}{record.getMessage()}{Style.RESET_ALL}"

        return f"{log_color}{record.asctime} - {record.name} - {record.levelname} - {record.message}{Style.RESET_ALL}"


class ColoredCsiFormatter(logging.Formatter):
    FORMATS = {
        'asctime': Fore.CYAN,
        'name': Fore.GREEN,
        'levelname': Fore.YELLOW,
        'message': Fore.WHITE
    }

    LOG_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        log_color = self.LOG_COLORS.get(record.levelno, Fore.WHITE)
        record.asctime = f"{self.FORMATS['asctime']}{self.formatTime(record, self.datefmt)}{Style.RESET_ALL}"
        record.name = f"{self.FORMATS['name']}{record.name}{Style.RESET_ALL}"
        record.levelname = f"{self.FORMATS['levelname']}{record.levelname}{Style.RESET_ALL}"
        record.message = f"{self.FORMATS['message']}{record.getMessage()}{Style.RESET_ALL}"

        return f"{log_color}{record.asctime} - {record.name} - {record.levelname} - {record.message}{Style.RESET_ALL}"

def setup_logging(session_id, log_level=logging.INFO):
    setup_csi_logging(session_id, log_level)
    setup_image_logging(session_id, log_level)


def setup_csi_logging(session_id, log_level=logging.INFO):
    logger = logging.getLogger('csi_acquisition')

    log_dirpath = Path('logs') / session_id
    os.makedirs(log_dirpath, exist_ok=True)
    file_handler = logging.FileHandler(log_dirpath / 'csi_acquisition.log', mode='w')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    colored_formatter = ColoredCsiFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(colored_formatter)
    logger.addHandler(stream_handler)

    logger.setLevel(log_level)

    # ルートロガーからのハンドラーの継承を無効化
    logger.propagate = False

def setup_image_logging(session_id, log_level=logging.INFO):
    logger = logging.getLogger('image_acquisition')

    log_dirpath = Path('logs') / session_id
    os.makedirs(log_dirpath, exist_ok=True)
    file_handler = logging.FileHandler(log_dirpath / 'image_acquisition.log', mode='w')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    colored_formatter = ColoredImageFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(colored_formatter)
    logger.addHandler(stream_handler)

    logger.setLevel(log_level)

    # ルートロガーからのハンドラーの継承を無効化
    logger.propagate = False

def setup_root_logging(log_level=logging.INFO):
    # ルートロガーを取得
    root_logger = logging.getLogger()
    
    # 既存のハンドラーがある場合は削除
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # ストリームハンドラーを追加（標準出力にログを出力）
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    
    # ルートロガーにハンドラーを追加
    root_logger.addHandler(stream_handler)
    
    # ログレベルを設定
    root_logger.setLevel(log_level)