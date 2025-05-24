# ui_dashboard.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox, QFrame
from PySide6.QtCore import Qt, QTimer, QThreadPool
from omronfins.finsudp import FinsUDP
from algo_fins_test import CheckConnectionWorker

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.fins = None
        self.comm_alive = False
        self.prev_bit = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.thread_pool = QThreadPool()
        self.init_ui()

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
        row1.addWidget(self.test1_lamp_label)
        row1.addWidget(self.test1_lamp_text_label)

        row2 = QHBoxLayout()
        row2.addWidget(self.test2_lamp_label)
        row2.addWidget(self.test2_lamp_text_label)
        row2.addWidget(self.test3_lamp_label)
        row2.addWidget(self.test3_lamp_text_label)

        status_layout = QVBoxLayout()
        status_layout.addLayout(row1)
        status_layout.addLayout(row2)

        status_group.setLayout(status_layout)
        self.layout.addWidget(status_group, alignment=Qt.AlignRight)

    def init_status_lamps(self):
        self.comm_lamp_label = QLabel()
        self.comm_lamp_label.setFixedSize(20, 20)
        self.comm_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.test1_lamp_label = QLabel()
        self.test1_lamp_label.setFixedSize(20, 20)
        self.test1_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.test2_lamp_label = QLabel()
        self.test2_lamp_label.setFixedSize(20, 20)
        self.test2_lamp_label.setStyleSheet("background-color: #A8E6CF; border-radius: 10px;")

        self.test3_lamp_label = QLabel()
        self.test3_lamp_label.setFixedSize(20, 20)
        self.test3_lamp_label.setStyleSheet("background-color: #FF8A80; border-radius: 10px;")

    def init_status_labels(self):
        self.comm_lamp_text_label = QLabel("통신 안 됨")
        self.comm_lamp_text_label.setStyleSheet("color: Red; font-weight: bold;")

        self.test1_lamp_text_label = QLabel("TEST1")
        self.test2_lamp_text_label = QLabel("TEST2")
        self.test3_lamp_text_label = QLabel("TEST3")

        for lbl in [self.test1_lamp_text_label, self.test2_lamp_text_label, self.test3_lamp_text_label]:
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

        ip_layout.addWidget(QLabel("PLC IP : "))
        ip_layout.addWidget(self.ip_input)
        ip_layout.addWidget(self.connect_btn)

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
            self.fins = FinsUDP(0, 11)
            self.fins.open(ip, 9600)
            self.fins.set_destination(dst_net_addr=0, dst_node_num=10, dst_unit_addr=0)
            self.comm_alive = True
            self.status_label.setText(f"Socket open 성공: {ip}")
            self.status_label.setStyleSheet("color: Green; font-weight: bold;")
            self.timer.start(1000)

        except Exception as e:
            self.comm_alive = False
            self.status_label.setText(f"Socket open 실패: {e}")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")

    def check_connection(self):
        if not self.fins:
            self.status_label.setText("FINS 연결 안 됨")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")
            return

        worker = CheckConnectionWorker(self.fins, self.prev_bit, self.handle_connection_result)
        self.thread_pool.start(worker)

    def handle_connection_result(self, bit_val, is_alive, error):
        if error:
            self.status_label.setText(f"통신 실패 : {error}")
            self.status_label.setStyleSheet("color: Red; font-weight: bold;")
            self.comm_alive = False
            self.update_lamp(False)
        else:
            self.comm_alive = is_alive
            self.status_label.setText("통신 정상" if is_alive else "비트 변화 없음")
            self.status_label.setStyleSheet("color: Green; font-weight: bold;")
            self.prev_bit = bit_val
            self.update_lamp(is_alive)

    def update_lamp(self, is_alive):
        if is_alive:
            self.comm_lamp_label.setStyleSheet("background-color: #A8E6CF; border-radius: 10px;")
            self.comm_lamp_text_label.setText(f"통신 정상 {self.ip_input.text().strip()}")
            self.comm_lamp_text_label.setStyleSheet("color: Green; font-weight: bold;")
        else:
            self.comm_lamp_label.setStyleSheet("background-color: #FF8A80; border-radius: 10px;")
            self.comm_lamp_text_label.setText(f"통신 끊김 {self.ip_input.text().strip()}")
            self.comm_lamp_text_label.setStyleSheet("color: Red; font-weight: bold;")

