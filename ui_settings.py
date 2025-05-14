# ui_settings.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel("설정 페이지입니다.")
        label.setStyleSheet("color: white; font-size: 16px; padding: 10px;")
        layout.addWidget(label)
        layout.addStretch()
