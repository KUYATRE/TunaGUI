from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox, QFrame
from PySide6.QtCore import Qt, QTimer, QThreadPool
from algo_fins_comm import FinsUDPClient
from algo_fins_checkconnection import CheckConnectionWorker

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.fins = None
        self.comm_alive = False
        self.prev_bit = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.thread_pool = QThreadPool()

        self.heartbeat_area = 0xA0
        self.heartbeat_word = 0
        self.heartbeat_bit = 0
        self.heartbeat_state = False
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.toggle_heartbeat)
        self.plc_hb_signal = False

        self.init_ui()

    @staticmethod
    def get_default_config():
        return {
            'ip': '172.22.80.1',
            'plc_port': 9600,
            'plc_node': 1,
            'pc_node': 179
        }

    def get_plc_ip(self) -> str:
        return self.ip_input.text().strip()

    def init_ui(self):
        self.settings_group = QGroupBox()
        self.layout = QVBoxLayout(self)
        self.add_status_group()
        self.add_horizontal_separator()
        self.add_main_connection_area()

    def add_status_group(self):
        self.init_status_lamps()
        self.init_status_labels()

        status_group = QGroupBox("상태 표시", alignment=Qt.AlignCenter)
        status_group.setFixedSize(500, 120)

        row1 = QHBoxLayout()
        row1.addWidget(self.comm_lamp_label)
        row1.addWidget(self.comm_lamp_text_label)
        row1.addWidget(self.hb_pc_lamp_label)
        row1.addWidget(self.hb_pc_lamp_text_label)

        row2 = QHBoxLayout()
        row2.addWidget(self.test2_lamp_label)
        row2.addWidget(self.test2_lamp_text_label)
        row2.addWidget(self.hb_plc_lamp_label)
        row2.addWidget(self.hb_plc_lamp_text_label)

        status_layout = QVBoxLayout()
        status_layout.addLayout(row1)
        status_layout.addLayout(row2)

        status_group.setLayout(status_layout)
        self.layout.addWidget(status_group, alignment=Qt.AlignRight)

    def init_status_lamps(self):
        self.comm_lamp_label = QLabel()
        self.comm_lamp_label.setFixedSize(20, 20)
        self.comm_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.hb_pc_lamp_label = QLabel()
        self.hb_pc_lamp_label.setFixedSize(20, 20)
        self.hb_pc_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.test2_lamp_label = QLabel()
        self.test2_lamp_label.setFixedSize(20, 20)
        self.test2_lamp_label.setStyleSheet("background-color: #A8E6CF; border-radius: 10px;")

        self.hb_plc_lamp_label = QLabel()
        self.hb_plc_lamp_label.setFixedSize(20, 20)
        self.hb_plc_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

    def init_status_labels(self):
        self.comm_lamp_text_label = QLabel("통신 안 됨")
        self.comm_lamp_text_label.setStyleSheet("color: Red; font-weight: bold;")

        self.hb_pc_lamp_text_label = QLabel("Heartbeat(PC)")
        self.test2_lamp_text_label = QLabel("TEST2")
        self.hb_plc_lamp_text_label = QLabel("Heartbeat(PLC)")

        for lbl in [self.hb_pc_lamp_text_label, self.test2_lamp_text_label, self.hb_plc_lamp_text_label]:
            lbl.setStyleSheet("font-weight: bold;")

    def add_horizontal_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        self.layout.addWidget(line)

    def add_main_connection_area(self):
        main_split_layout = QHBoxLayout()
        left = self.create_left_connection_layout()
        vline = self.create_vertical_separator()
        right = self.create_right_placeholder_layout()

        main_split_layout.addLayout(left)
        main_split_layout.addWidget(vline)
        main_split_layout.addLayout(right)

        self.layout.addLayout(main_split_layout)

    def create_left_connection_layout(self):
        layout = QVBoxLayout()

        ip_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("예: 172.22.80.1")

        self.connect_btn = QPushButton("연결")
        self.connect_btn.clicked.connect(self.try_connect)

        self.disconnect_btn = QPushButton("해제")
        self.disconnect_btn.clicked.connect(self.disconnect)
        self.disconnect_btn.setEnabled(False)

        ip_layout.addWidget(QLabel("PLC IP : "))
        ip_layout.addWidget(self.ip_input)
        ip_layout.addWidget(self.connect_btn)
        ip_layout.addWidget(self.disconnect_btn)

        self.status_label = QLabel("PLC 연결 안 됨")
        self.status_label.setStyleSheet("color: Red; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignLeft)

        layout.addLayout(ip_layout)
        layout.addWidget(self.status_label)

        return layout

    def create_vertical_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def create_right_placeholder_layout(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("우측 내용 placeholder"))
        return layout

    def try_connect(self):
        ip = self.ip_input.text().strip()
        if not ip:
            self.status_label.setText("IP를 입력하세요.")
            return

        try:
            self.plc_port = 9600
            self.plc_node = 1
            self.pc_node = 179
            self.fins = FinsUDPClient(ip, plc_port=self.plc_port, plc_node=self.plc_node, pc_node=self.pc_node)
            test_bit = self.fins.read_word_bit(mem_area=0xA0, word_addr=0, bit_offset=0)
            if test_bit is None:
                raise Exception("PLC 응답 없음")

            success = self.fins.write_word_bit(mem_area=0xA0, word_addr=16800, bit_offset=0, turn_on=True)
            if not success:
                raise Exception("초기 비트 쓰기 실패")

            self.comm_alive = True
            self.status_label.setText(f"소켓 연결 성공: {ip}")
            self.status_label.setStyleSheet("color: Green; font-weight: bold;")

            self.timer.start(500)
            self.heartbeat_timer.start(500)

            self.disconnect_btn.setEnabled(True)
            self.connect_btn.setEnabled(False)

        except Exception as e:
            self.comm_alive = False
            self.status_label.setText(f"소켓 연결 실패: {e}")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")

    def toggle_heartbeat(self):
        if self.fins:
            success = False
            try:
                success = self.fins.write_word_bit(mem_area=0xA0, word_addr=16800, bit_offset=1, turn_on=self.heartbeat_state)
            except Exception as e:
                print("PC → PLC Heartbeat 쓰기 오류:", e)

            self.update_pc_hb_lamp(self.heartbeat_state if success else False)
            self.heartbeat_state = not self.heartbeat_state

    def check_connection(self):
        if not self.fins:
            self.status_label.setText("FINS 클라이언트 없음")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")
            return

        worker = CheckConnectionWorker(
            fins_client=self.fins,
            prev_bit=self.prev_bit,
            callback=self.handle_connection_result,
            mem_area=self.heartbeat_area,
            word_addr=self.heartbeat_word,
            bit_offset=self.heartbeat_bit
        )
        self.thread_pool.start(worker)

    def handle_connection_result(self, bit_val, is_alive, error):
        if error:
            self.status_label.setText(f"통신 실패 : {error}")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")
            self.comm_alive = False
            self.update_comm_lamp(False)
            self.update_plc_hb_lamp(False)
        else:
            self.comm_alive = is_alive
            self.status_label.setText("통신 정상" if is_alive else "비트 변화 없음")
            self.status_label.setStyleSheet("color: Green; font-weight: bold;")
            self.prev_bit = bit_val
            self.update_comm_lamp(is_alive)
            self.update_plc_hb_lamp(bit_val == 1)

    def disconnect(self):
        try:
            self.fins.write_word_bit(mem_area=0xA0, word_addr=16800, bit_offset=0, turn_on=False)
        except:
            pass

        if self.timer.isActive():
            self.timer.stop()
        if self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()

        if self.fins:
            try:
                self.fins.close()
            except:
                pass
            self.fins = None

        self.status_label.setText("연결 해제됨")
        self.status_label.setStyleSheet("color: Red; font-weight: bold;")
        self.comm_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")
        self.comm_lamp_text_label.setText("통신 안 됨")
        self.comm_lamp_text_label.setStyleSheet("color: Red; font-weight: bold;")
        self.disconnect_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
        self.update_pc_hb_lamp(False)
        self.update_plc_hb_lamp(False)

    def update_comm_lamp(self, is_alive):
        color = "#A8E6CF" if is_alive else "#FF8A80"
        text = "통신 정상" if is_alive else "통신 끊김"
        font_color = "Green" if is_alive else "Red"
        self.comm_lamp_label.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
        self.comm_lamp_text_label.setText(f"{text} {self.ip_input.text().strip()}")
        self.comm_lamp_text_label.setStyleSheet(f"color: {font_color}; font-weight: bold;")

    def update_pc_hb_lamp(self, is_alive):
        color = "#A8E6CF" if is_alive else "lightgray"
        self.hb_pc_lamp_label.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
        self.hb_pc_lamp_text_label.setText("Heartbeat(PC)")
        self.hb_pc_lamp_text_label.setStyleSheet("color: black; font-weight: bold;")

    def update_plc_hb_lamp(self, is_alive):
        color = "#A8E6CF" if is_alive else "lightgray"
        self.hb_plc_lamp_label.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
        self.hb_plc_lamp_text_label.setText("Heartbeat(PLC)")
        self.hb_plc_lamp_text_label.setStyleSheet("color: black; font-weight: bold;")
