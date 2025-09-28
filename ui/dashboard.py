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
        # 자동 시작 제거
        self.is_reconnecting = False

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 통신 상태 그룹
        self.status_group = QGroupBox("통신 상태")
        status_layout = QHBoxLayout()
        
        # 하트비트 램프
        self.heartbeat_lamp = QLabel()
        self.heartbeat_lamp.setFixedSize(30, 30)
        self.heartbeat_lamp.setStyleSheet(LAMP_COLOR['default'])
        status_layout.addWidget(QLabel("Heartbeat"))
        status_layout.addWidget(self.heartbeat_lamp)
        
        # 연결/해제 버튼 추가
        self.connect_btn = QPushButton("연결")
        self.connect_btn.clicked.connect(self.start_communication)
        self.disconnect_btn = QPushButton("해제")
        self.disconnect_btn.clicked.connect(self.stop_communication)
        self.disconnect_btn.setEnabled(False)
        
        status_layout.addWidget(self.connect_btn)
        status_layout.addWidget(self.disconnect_btn)
        self.status_group.setLayout(status_layout)

        self.ip_input = QLineEdit()
        self.ip_input.setText("172.22.80.1")

        # 나머지 UI 요소들...
        layout.addWidget(self.status_group)
        layout.addWidget(QLabel("PLC IP 주소"))
        layout.addWidget(self.ip_input)

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

    def start_communication(self):
        """통신 시작"""
        try:
            if self.fins is None:
                plc_ip = self.ip_input.text()
                self.fins = FinsUDPClient(plc_ip)
            
            self.is_reconnecting = self.setup_heartbeat_monitor()
            self.setup_trigger_monitor(self.is_reconnecting)
            
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.ip_input.setEnabled(False)
            logger.info("통신 시작됨")
        except Exception as e:
            logger.error(f"통신 시작 실패: {e}")
            self.on_heartbeat_error(str(e))

    def stop_communication(self):
        """통신 중지"""
        try:
            if self.heartbeat_monitor:
                self.heartbeat_monitor.stop()
            if self.trigger_monitor:
                self.trigger_monitor.stop()
                
            self.heartbeat_lamp.setStyleSheet(LAMP_COLOR['default'])
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.ip_input.setEnabled(True)
            logger.info("통신 중지됨")
        except Exception as e:
            logger.error(f"통신 중지 실패: {e}")