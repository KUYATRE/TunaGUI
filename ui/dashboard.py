# ui/dashboard.py - HeartbeatMonitor + ThetaAnalyzer 연동 (리소스 최적화 버전)

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFrame, QLineEdit, QTableWidget, QTableWidgetItem, QComboBox
)
from services.fins_comm import FinsUDPClient
from services.heartbeat_monitor import HeartbeatMonitor
from services.log_analyzer import ensure_dataset_dir
from services.trigger_monitor import TriggerMonitor
from services.data_processor import DataProcessor
from ui.dashboard_controller import DashboardController
from utils.theta_analyzer import ThetaAnalyzer

LAMP_COLOR = {
    'default': "background-color: gray; border-radius: 15px;",
    'active': "background-color: green; border-radius: 15px;",
    'error': "background-color: red; border-radius: 15px;"
}

# 기존 logger 설정 개선
logger = logging.getLogger("heartbeat_logger")  # 고유 이름 지정
logger.setLevel(logging.DEBUG)

# 핸들러가 없을 경우만 추가 (중복 방지)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)  # 핸들러에도 level 명시
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# 아래와 같이 DEBUG 로그 출력 테스트
logger.debug("디버그 로그 출력 확인용")

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.fins = None
        self.heartbeat_monitor = None
        self.trigger_monitor = None
        self.base_dir = ensure_dataset_dir()

        self.processor = DataProcessor(self.base_dir)

        self.selected_zone_number = 1

        self.controller = None
        self.theta_df = []
        self.theta_analyzer = ThetaAnalyzer()
        self.init_ui()
        self.is_reconnecting = self.setup_heartbeat_monitor()
        self.setup_trigger_monitor(self.is_reconnecting)

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.status_group = QGroupBox("통신 상태")
        status_layout = QHBoxLayout()
        self.heartbeat_lamp = QLabel()
        self.heartbeat_lamp.setFixedSize(30, 30)
        self.heartbeat_lamp.setStyleSheet(LAMP_COLOR['default'])
        status_layout.addWidget(QLabel("Heartbeat"))
        status_layout.addWidget(self.heartbeat_lamp)
        self.status_group.setLayout(status_layout)

        self.ip_input = QLineEdit()
        self.ip_input.setText("172.22.80.1")

        self.zone_selector = QComboBox()
        self.zone_selector.addItems([f"ZONE {i}" for i in range(1, 9)])
        self.zone_selector.currentIndexChanged.connect(self.update_selected_zone)

        self.path_input = QLineEdit()
        self.path_input.setText(ensure_dataset_dir())

        self.theta_table = QTableWidget()
        self.theta_table.setColumnCount(0)
        self.theta_table.setRowCount(0)

        self.table_widget = QTableWidget()

        self.controller = DashboardController(
            table_widget=self.table_widget,
            theta_table=self.theta_table,
            theta_analyzer=self.theta_analyzer
        )

        layout.addWidget(self.status_group)
        layout.addWidget(QLabel("PLC IP 주소"))
        layout.addWidget(self.ip_input)
        layout.addWidget(QLabel("ZONE 선택"))
        layout.addWidget(self.zone_selector)
        layout.addWidget(QLabel("Theta 분석 결과"))
        layout.addWidget(self.theta_table)
        layout.addWidget(QLabel("데이터 테이블"))
        layout.addWidget(self.table_widget)
        # layout.addWidget(QLabel("데이터 시각화"))
        # layout.addWidget(self.controller.canvas)
        layout.addWidget(QLabel("데이터 경로"))
        layout.addWidget(self.path_input)

    def update_selected_zone(self, index):
        self.selected_zone_number = index + 2
        logger.debug(f"Zone selector changed to: {self.selected_zone_number}")
        self.refresh_display()

    def setup_heartbeat_monitor(self):
        if self.fins is None:
            plc_ip = self.ip_input.text()
            self.fins = FinsUDPClient(plc_ip)

        logger.info("Heater beat signal reading...")

        self.heartbeat_monitor = HeartbeatMonitor(
            fins_client=self.fins,
            mem_area=0xA0,
            word_addr=0,
            bit_offset=0,
            interval_ms=500
        )
        self.heartbeat_monitor.bit_changed.connect(self.on_heartbeat_update)
        self.heartbeat_monitor.error_occurred.connect(self.on_heartbeat_error)
        self.heartbeat_monitor.start()

        logger.debug(f"Heartbeat reconnection: reconnecting({self.heartbeat_monitor.is_reconnecting})")

        return self.heartbeat_monitor.is_reconnecting

    def on_heartbeat_update(self, bit_value, is_changed):
        logger.debug(f"Heartbeat update - bit: {bit_value}, changed: {is_changed}")
        self.heartbeat_lamp.setStyleSheet(
            LAMP_COLOR['active'] if bit_value else LAMP_COLOR['default']
        )

    def on_heartbeat_error(self, msg):
        logger.error(f"Heartbeat error: {msg}")
        self.heartbeat_lamp.setStyleSheet(LAMP_COLOR['error'])

    def setup_trigger_monitor(self, is_reconnecting):
        if self.fins is None:
            plc_ip = self.ip_input.text()
            self.fins = FinsUDPClient(plc_ip)

        logger.info("Trigger monitor started...")

        self.trigger_monitor = TriggerMonitor(
            fins_client=self.fins,
            is_reconnecting=is_reconnecting,
            interval_ms=500
        )
        self.trigger_monitor.data_received.connect(self.on_trigger_data_received)
        self.trigger_monitor.error_occurred.connect(self.on_trigger_error)
        self.theta_df, tube_id = self.controller.run_all_zone_analysis(self.base_dir, self.selected_zone_number)
        self.trigger_monitor.start()

        self.processor.save_regression_data(tube_id, self.theta_df)

    def on_trigger_error(self, msg):
        logger.error(f"Trigger detect error: {msg}")

    def on_trigger_data_received(self, tube_id, job_id):
        logger.info(f"[Trigger] Received TubeID: {tube_id}, JobID: {job_id}")
        self.refresh_display()

    def refresh_display(self):
        base_dir = self.path_input.text()
        df, zone = self.controller.load_latest_merge_csv(base_dir, self.selected_zone_number)
        logger.debug(f"Data refresh for zone number: {zone}")
        if df is not None:
            logger.debug(f"Refreshed dataframe shape: {df.shape}")
            self.controller.display_dataframe(df)
            try:
                self.controller.run_regression_and_plot(df, zone)
            except Exception as e:
                logger.exception("Regression plot error:")


    def get_latest_merge_filepath(self, base_dir: str):
        from pathlib import Path
        base_path = Path(base_dir)
        merge_files = sorted(base_path.rglob("*MERGE*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
        return str(merge_files[0]) if merge_files else None
