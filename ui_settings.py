# ui_settings.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtCore import Qt
from omronfins.finsudp import FinsUDP, datadef

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.fins = None
        self.comm_alive = False
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # === IP 입력 필드 ===
        ip_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("예: 172.22.80.1")
        self.connect_btn = QPushButton("연결")
        self.connect_btn.clicked.connect(self.try_connect)

        ip_layout.addWidget(QLabel("PLC IP:"))
        ip_layout.addWidget(self.ip_input)
        ip_layout.addWidget(self.connect_btn)

        self.layout.addLayout(ip_layout)

        # === 상태 표시 ===
        self.status_label = QLabel("PLC 연결 안 됨")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)

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
            self.status_label.setText(f"PLC 연결 성공: {ip}")
        except Exception as e:
            self.comm_alive = False
            self.status_label.setText(f"연결 실패: {e}")
