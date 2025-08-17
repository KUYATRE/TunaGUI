from PySide6.QtCore import QObject, QTimer, Signal
from services.fins_comm import FinsUDPClient
import socket
import time
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
        self.failure_count = 0
        self.max_failures = 3
        self.is_reconnecting = False
        self.trigger_monitor = None

        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.check_bit)

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(60000)  # 1분마다 재시도
        self.reconnect_timer.timeout.connect(self.try_restart_monitor)

        if hasattr(self.fins, 'socket'):
            try:
                self.fins.socket.settimeout(1.0)
            except Exception:
                logger.warning("FINS 소켓 타임아웃 설정 실패")

    def attach_trigger_monitor(self, trigger_monitor):
        self.trigger_monitor = trigger_monitor

    def start(self):
        logger.info("HeartbeatMonitor 시작됨")
        self.timer.start()

    def stop(self):
        logger.info("HeartbeatMonitor 중단됨")
        self.timer.stop()

    def try_restart_monitor(self):
        logger.info("HeartbeatMonitor 재시도 시작")
        self.reconnect_timer.stop()
        self.is_reconnecting = False
        if self.trigger_monitor:
            logger.debug("TriggerMonitor 재연결 해제")
            self.trigger_monitor.set_reconnecting(False)
        self.failure_count = 0
        self.start()

    def check_bit(self):
        if self.is_reconnecting:
            logger.debug(f"재연결 대기 중 - check_bit 실행 안됨: reconnecting({self.is_reconnecting})")
            return

        try:
            bit_val = self.fins.read_word_bit(
                mem_area=self.mem_area,
                word_addr=self.word_addr,
                bit_offset=self.bit_offset
            )

            if bit_val is None:
                raise TimeoutError("응답 없음 (PLC 연결 문제?)")

            is_changed = (self.prev_bit is None) or (bit_val != self.prev_bit)
            self.prev_bit = bit_val

            logger.debug(f"Heartbeat 수신 - bit: {bit_val}, 변경 여부: {is_changed}")
            self.failure_count = 0
            self.bit_changed.emit(bit_val, is_changed)

        except (socket.timeout, TimeoutError) as e:
            logger.warning(f"통신 타임아웃 발생: {e}")
            self.stop()
            self.is_reconnecting = True
            logger.debug(f"Communication timeout: reconnecting({self.is_reconnecting})")
            self.reconnect_timer.start()
            self.error_occurred.emit(f"Heartbeat 중단됨: {str(e)} (1분 후 재시도)")

        except Exception as e:
            logger.exception("Heartbeat 예외 발생")
            self.stop()
            self.is_reconnecting = True
            logger.debug(f"Heartbeat exeption occured: reconnecting({self.is_reconnecting})")
            self.reconnect_timer.start()
            self.error_occurred.emit(f"예외 발생: {str(e)} (1분 후 재시도)")
