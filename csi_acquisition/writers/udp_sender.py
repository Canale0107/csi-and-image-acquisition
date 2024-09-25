import logging
import socket
import threading

from csi_acquisition.csi.meta_csi_data import MetaCsiData
from csi_acquisition.writers.abstract_writer import DataWriter, WriterManager

logger = logging.getLogger(__name__)

class UdpSender(DataWriter):
    def __init__(self, sock, receivers):
        self.sock = sock
        self.receivers = receivers

    def send_to_receiver(self, message, receiver):
        try:
            addr = (receiver['ip'], receiver['port'])
            self.sock.sendto(message, addr)
            logger.debug("Sent message to %s: %s", addr, message)
        except OSError as e:
            logger.error("Failed to send message to %s: %s", addr, e)

    def write_data(self, meta_csi_data: MetaCsiData):
        # メッセージのエンコード
        line = ','.join(map(str, meta_csi_data.to_dict().values()))
        message = line.encode('utf-8')
        
        # 各レシーバーごとにスレッドを生成してメッセージを送信
        threads = []
        for receiver in self.receivers:
            thread = threading.Thread(target=self.send_to_receiver, args=(message, receiver))
            thread.start()
            threads.append(thread)
        
        # 全てのスレッドの終了を待機
        for thread in threads:
            thread.join()


class UdpSenderManager(WriterManager):
    def __init__(self, config):
        self.sock = None
        self.config = config

    def __enter__(self):
        # UDPソケットの作成
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self
    
    def get_writer(self):
        # UdpSenderオブジェクトを返す
        receivers = self.config.receiver_ips_ports
        return UdpSender(self.sock, receivers)

    def __exit__(self, exc_type, exc_value, traceback):
        # ソケットを閉じる
        if self.sock:
            self.sock.close()
