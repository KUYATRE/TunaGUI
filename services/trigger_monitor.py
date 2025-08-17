from PySide6.QtCore import QObject, QTimer, Signal
from services.fins_comm import FinsUDPClient
from services.data_processor import DataProcessor

class TriggerMonitor(QObject):
    data_received = Signal(int, int)  # tube_id, job_id
    error_occurred = Signal(str)

    def __init__(self, fins_client: FinsUDPClient, is_reconnecting, interval_ms=2000):
        super().__init__()
        self.fins = fins_client
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.check_trigger)
        self.enabled = False

        # 트리거 조건 설정
        self.mem_area = 0xA0
        self.word_addr = 0
        self.bit_offset = 3
        self.prev_state = 0

        self.tube_id = 0
        self.job_id = 0

        self.is_reconnecting = is_reconnecting

    def start(self):
        self.enabled = True
        self.timer.start()

    def stop(self):
        self.enabled = False
        self.timer.stop()

    def check_trigger(self):
        if self.is_reconnecting:
            print(f"reconnecting: {self.is_reconnecting}")
            return

        try:
            bit = self.fins.read_word_bit(
                mem_area=self.mem_area,
                word_addr=self.word_addr,
                bit_offset=self.bit_offset
            )
            print(f"[Trigger] Bit: {bit}, Prev: {self.prev_state}")

            # 상승 에지 (0 -> 1) 감지
            if self.prev_state == 0 and bit == 1:
                job_id = self.fins.read_word(
                    mem_area=0xA2,
                    word_addr=1
                )
                print(f"[Trigger] Job ID: {job_id}")

                processor = DataProcessor(job_id)
                process_data = processor.extract_drivein_mean()
                print(f"Process data refined: {process_data}")

                self.tube_id, self.job_id, sheet_res_data = processor.data_receive_plc(fins_client=self.fins)
                print(f"Data received: Tube ID: {self.tube_id}, Job ID: {self.job_id}")

                self.data_received.emit(self.tube_id, self.job_id)

                rsheet_data = processor.save_sheet_resistance(sheet_res_data)
                print(f"Rsheet data refined: {rsheet_data}")

                processor.merge_files()
                print(f"MERGE CSV file generated")

            self.prev_state = bit

        except Exception as e:
            self.error_occurred.emit(str(e))
