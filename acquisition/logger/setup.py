import os
from pathlib import Path
import logging
from colorama import Fore, Style, init

# 初期化 (Windows 対応)
init(autoreset=True)

# カスタムフォーマッター
class ColoredFormatter(logging.Formatter):
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

# ロガーをセットアップする関数
def setup_logger(session_id, log_level=logging.INFO):
    logger = logging.getLogger()

    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler(Path('logs') / f'{session_id}.log', mode='a')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    colored_formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(colored_formatter)
    logger.addHandler(stream_handler)

    logger.setLevel(log_level)

    return logger

def setup_shared_logger():
    shared_logger = logging.getLogger('shared_logger')

    shared_handler = logging.StreamHandler()
    formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    shared_handler.setFormatter(formatter)

    shared_logger.addHandler(shared_handler)
    shared_logger.setLevel(logging.INFO)

    return shared_logger