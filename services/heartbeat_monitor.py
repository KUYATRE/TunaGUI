# services/heartbeat_monitor.py

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtCore import QRunnable, Signal, QObject
from services.fins_comm import FinsUDPClient

class HeartbeatMonitor(QObject):
    bit_changed = Signal(int, bool)     # (bit_value, is_changed)
    error_occurred = Signal(str)        # (error message)

    def __init__(self, fins_client, mem_area, word_addr, bit_offset, interval_ms=1000, parent=None):
        super().__init__(parent)
        self.fins = fins_client
        self.mem_area = mem_area
        self.word_addr = word_addr
        self.bit_offset = bit_offset
        self.prev_bit = None

        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.check_bit)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def check_bit(self):
        try:
            bit_val = self.fins.read_word_bit(
                mem_area=self.mem_area,
                word_addr=self.word_addr,
                bit_offset=self.bit_offset
            )

            if bit_val is None:
                raise Exception("응답 없음 (PLC 연결 문제?)")

            is_changed = (self.prev_bit is None) or (bit_val != self.prev_bit)
            self.prev_bit = bit_val

            self.bit_changed.emit(bit_val, is_changed)

        except Exception as e:
            self.error_occurred.emit(str(e))


class ConnectionSignalEmitter(QObject):
    result = Signal(bool)


class CheckConnectionWorker(QRunnable):
    def __init__(self, fins_client: FinsUDPClient, mem_area=0xA0, word=0, bit=0):
        super().__init__()
        self.fins = fins_client
        self.mem_area = mem_area
        self.word = word
        self.bit = bit
        self.signals = ConnectionSignalEmitter()

    def run(self):
        try:
            data = self.fins.read_bit(self.mem_area, self.word, self.bit)
            is_alive = bool(data)
        except Exception:
            is_alive = False
        self.signals.result.emit(is_alive)
