import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QGroupBox, QComboBox, QFormLayout, QTableWidget, QTableWidgetItem, QSizePolicy
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import os

from services.log_analyzer import (
    get_file,
    get_any_data_from_column,
    save_tuning_parameter_rows,
    extract_t_data,
    read_csv_by_classified_data
)
from utils.heater_analysis import consol_controller
from utils.plot_utils import extract_all_zones_all_series_limited, detect_heater_zones
from utils.fins_data_sender import data_send

# Process log path : 실제 경로로 수정 필요
PROCESS_LOG_PATH = r"C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets"

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러 설정
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 로그 포맷 설정
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 핸들러 추가
logger.addHandler(console_handler)


class TuningPage(QWidget):
    def __init__(self, dashboard):
        super().__init__()
        self.data_rows = []
        self.zone_data = {}
        self.selected_temp_mode = "normal"
        self.selected_etype = "BCl3"
        self.tuning_data = None
        self.classified_tuning_data = None
        self.dashboard = dashboard
        self.dashboard.tuning_data_to_page.connect(self.update_tuning_data)

        # matplotlib 캔버스 초기화
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        self.init_ui()
        self.selected_log_filename = ""
        self.tube_id = 0
        self.job_id = 0

    def init_ui(self):
        layout = QVBoxLayout(self)

        # === 파일 업로드 ===
        file_layout = QHBoxLayout()
        self.upload_btn = QPushButton("\U0001F4C1")
        self.upload_btn.setFixedSize(40, 40)
        self.upload_btn.setStyleSheet("background-color: #5e35b1; color: white; font-size: 20px")
        self.upload_btn.clicked.connect(self.load_csv)

        self.file_label = QLabel("선택된 파일 없음")
        self.file_label.setStyleSheet("color: red; font-style: italic; font-weight: bold;")

        file_group = QGroupBox()
        file_group.setStyleSheet("background-color: lightgray")
        file_group_layout = QVBoxLayout()
        file_group_layout.addWidget(self.file_label)
        file_group.setLayout(file_group_layout)
        file_group.setMinimumWidth(400)

        file_layout.addWidget(self.upload_btn)
        file_layout.addWidget(file_group)

        # === 설정 필드 ===
        settings_layout = QHBoxLayout()
        gear_label = QLabel("\u2699\ufe0f")
        gear_label.setFixedSize(40, 40)
        gear_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gear_label.setStyleSheet("background-color: #5e35b1; color: white; font-size: 20px")
        settings_layout.addWidget(gear_label)

        config_group = QGroupBox()
        config_group.setStyleSheet("background-color: lightgray")
        form_layout = QFormLayout()

        self.temp_mode_combo = QComboBox()
        self.temp_mode_combo.addItems(["normal", "high"])
        self.temp_mode_combo.currentTextChanged.connect(lambda text: setattr(self, "selected_temp_mode", text))

        self.etype_combo = QComboBox()
        self.etype_combo.addItems(["BCl3", "Annealing", "POCl3", "Oxidation"])
        self.etype_combo.currentTextChanged.connect(lambda text: setattr(self, "selected_etype", text))

        form_layout.addRow("Temp Control Mode 선택", self.temp_mode_combo)
        form_layout.addRow("설비군 선택", self.etype_combo)
        config_group.setLayout(form_layout)

        settings_layout.addWidget(config_group)

        self.analyze_btn = QPushButton("분석 실행")
        self.analyze_btn.setStyleSheet("background-color: #5e35b1; color: white;")
        self.analyze_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.analyze_btn.clicked.connect(self.run_analysis)
        settings_layout.addWidget(self.analyze_btn)

        # === 결과 / 테이블 / 그래프 ===
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("background-color: lightgray; color: green; font-style: italic; border: 2px solid #5e35b1; border-radius: 8px; padding: 4px;")

        # 테이블과 Apply 버튼을 위한 수평 레이아웃
        table_layout = QHBoxLayout()
        
        # 테이블 설정
        self.table = QTableWidget()
        self.table.setStyleSheet("font-family: 'Segoe UI'; font-size: 13px;")
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_click)
        table_layout.addWidget(self.table)
        
        # Apply 버튼 추가
        apply_button = QPushButton("Apply")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #5e35b1;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #7c4dff;
            }
        """)
        apply_button.clicked.connect(self.apply_tuning)
        apply_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        table_layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # ... (기존 레이아웃에 table_layout 추가)
        layout.addLayout(file_layout)
        layout.addLayout(settings_layout)
        layout.addWidget(self.result_label)
        layout.addLayout(table_layout)
        layout.addWidget(self.canvas)

    def apply_tuning(self):
        zone_count = detect_heater_zones(self.data_rows[0])

        for i in range(zone_count):
            data_send(0xA0, 840 + (i * 5), self.new_np1[i])
            data_send(0xA0, 841 + (i * 5), self.new_np2[i])
            data_send(0xA0, 842 + (i * 5), self.new_hp1[i])
            data_send(0xA0, 843 + (i * 5), self.new_hp2[i])

    def update_tuning_data(self, tuning_data):
        """대시보드로부터 튜닝 데이터 수신"""
        try:
            self.tuning_data = tuning_data
            logger.debug(f"튜닝 페이지 데이터 업데이트: {self.tuning_data}")

            if self.tuning_data is not None:
                classified_data = extract_t_data(self.tuning_data)
                logger.debug(f"분류된 튜닝 데이터: {classified_data}")
                logger.debug(f"Tuning data keys: {classified_data.keys()}")

                self.classified_tuning_data = classified_data
                
                # CSV 파일 읽기
                self.data_rows, self.selected_log_filename = read_csv_by_classified_data(PROCESS_LOG_PATH, classified_data)
                if not self.data_rows:
                    logger.warning("CSV 파일을 찾을 수 없거나 읽기 실패")
                else:
                    logger.debug(f"읽은 CSV 데이터: {self.data_rows[0]}")
                    self.run_analysis()

        except Exception as e:
            logger.error(f"튜닝 데이터 업데이트 중 오류: {str(e)}", exc_info=True)

    def update_table_with_tuning_data(self):
        """튜닝 데이터로 테이블 업데이트"""
        if not self.tuning_data:
            return

        try:
            headers = ["구분"] + [f"Zone{i}" for i in range(1, 9)] + ["비고"]
            rows = []

            # NP1, NP2, HP1, HP2 데이터 구성
            for param in ['NP1', 'NP2', 'HP1', 'HP2']:
                row = [param]
                for zone_num in range(1, 9):
                    zone_key = f'Z{zone_num}'
                    if zone_key in self.tuning_data and self.tuning_data[zone_key]:
                        value = self.tuning_data[zone_key].get(param, 0)
                        row.append(str(value))
                    else:
                        row.append("0")
                row.append("")  # 비고
                rows.append(row)

            # 테이블 업데이트
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(row_idx, col_idx, item)

            self.table.resizeColumnsToContents()
            logger.info("튜닝 테이블 업데이트 완료")

        except Exception as e:
            logger.error(f"테이블 업데이트 중 오류: {e}")

    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", "", "CSV files (*.csv)")
        if file_path:
            self.data_rows = get_file(file_path)
            self.file_label.setText(file_path)
            self.file_label.setStyleSheet("color: #00cc00; font-style: italic; font-weight: bold;")

            self.selected_log_filename = os.path.basename(file_path)
            logger.info(f"CSV 파일 로드 완료: {self.selected_log_filename}")
        return file_path

    def run_analysis(self):
        if not self.data_rows:
            self.result_label.setText("CSV 파일을 먼저 업로드하세요.")
            logger.warning("분석 실행 실패: CSV 파일 없음")
            return

        logger.info("튜닝 분석 시작")
        zone_count = detect_heater_zones(self.data_rows[0])


        if self.classified_tuning_data is None:
            headers = ["구분"] + [f"Zone{i + 1}" for i in range(zone_count)] + ["비고"]
            p1, initial_p2, p2, recipe_step = consol_controller(
                self.selected_temp_mode, self.selected_etype, self.data_rows)
            self.zone_data = extract_all_zones_all_series_limited(self.data_rows, recipe_step)
        else:
            headers = (["구분"] + [f"Zone{i + 1}" for i in range(zone_count)] + ["비고"])
            n_p1, n_initial_p2, n_p2, n_recipe_step = consol_controller(
                'normal', self.selected_etype, self.data_rows)
            self.zone_data = extract_all_zones_all_series_limited(self.data_rows, n_recipe_step)
            h_p1, h_initial_p2, h_p2, h_recipe_step = consol_controller(
                'high', self.selected_etype, self.data_rows)
            self.zone_data = extract_all_zones_all_series_limited(self.data_rows, h_recipe_step)

        self.tube_id = get_any_data_from_column(self.data_rows, 'Tube ID')
        self.job_id = get_any_data_from_column(self.data_rows, 'JobNo')

        logger.debug(f"Tube ID: {self.tube_id}, Job No: {self.job_id}")

        self.result_label.setText("분석 완료! (Zone 헤더 클릭으로 그래프 확인 가능)")

        self.current_np1 = [0] * zone_count
        self.current_np2 = [0] * zone_count
        self.new_np1 = [0] * zone_count
        self.new_np2 = [0] * zone_count
        self.current_hp1 = [0] * zone_count
        self.current_hp2 = [0] * zone_count
        self.new_hp1 = [0] * zone_count
        self.new_hp2 = [0] * zone_count

        for i in range(zone_count):
            if self.classified_tuning_data is not None:
                logger.debug(f"Tuning data exists")

                tuning_data_key = list(self.classified_tuning_data.keys())

                current_np1_zone = self.classified_tuning_data[tuning_data_key[0]][f'Z{i+1}']['NP1']
                current_np2_zone = self.classified_tuning_data[tuning_data_key[0]][f'Z{i+1}']['NP2']
                current_hp1_zone = self.classified_tuning_data[tuning_data_key[0]][f'Z{i+1}']['HP1']
                current_hp2_zone = self.classified_tuning_data[tuning_data_key[0]][f'Z{i+1}']['HP2']

                self.current_np1[i] = current_np1_zone
                self.current_np2[i] = current_np2_zone
                self.current_hp1[i] = current_hp1_zone
                self.current_hp2[i] = current_hp2_zone

            else:
                break

        for i in range(zone_count):
            if self.classified_tuning_data is not None:
                logger.debug(f"Tuning data exists")
                if (self.current_np1 == 0) and (self.current_np2 == 0):
                    logger.debug(f"First time for tuning: Current param(P1: {self.current_np1}, P2: {self.current_np2})")
                    self.new_np1[i] = n_p1[i]
                    self.new_np2[i] = n_initial_p2[i]
                    logger.debug(f"First time for tuning: New param(P1: {self.new_np1}, P2: {self.new_np2})")

                else:
                    logger.debug(f"Not first time for tuning: Current param(P1: {self.current_np1}, P2: {self.current_np2})")
                    self.new_np1[i] = self.current_np1[i] + n_p1[i]
                    if n_p1[i] == 0:
                        self.new_np2[i] = self.current_np2[i] + n_p2[i]
                    else:
                        self.new_np2[i] = self.current_np2[i]
                    logger.debug(f"Not first time for tuning: New param(P1: {self.new_np1}, P2: {self.new_np2})")

                if (self.current_hp1 == 0) and (self.current_hp2 == 0):
                    logger.debug(f"First time for tuning: Current param(P1: {self.current_hp1}, P2: {self.current_hp2})")
                    self.new_hp1[i] = h_p1[i]
                    self.new_hp2[i] = h_initial_p2[i]
                    logger.debug(f"First time for tuning: New param(P1: {self.new_hp1}, P2: {self.new_hp2})")

                else:
                    logger.debug(f"Not first time for tuning: Current param(P1: {self.current_hp1}, P2: {self.current_hp2})")
                    self.new_hp1[i] = self.current_hp1[i] + h_p1[i]
                    if h_p1[i] == 0:
                        self.new_hp2[i] = self.current_hp2[i] + h_p2[i]
                    else:
                        self.new_hp2[i] = self.current_hp2[i]
                    logger.debug(f"Not first time for tuning: New param(P1: {self.new_hp1}, P2: {self.new_hp2})")
            else:
                break

        if self.classified_tuning_data is not None:
            rows = [
                ["NP1"] + self.new_np1 + [""],
                ["NP2"] + self.new_np2 + [""],
                ["HP1"] + self.new_hp1 + [""],
                ["HP2"] + self.new_hp2 + [""]
            ]

        else:
            rows = [
                ["초기 P2"] + initial_p2 + ["※ 첫 튜닝시에 적용"],
                ["P1 조정"] + p1 + [""],
                ["P2 조정"] + p2 + [""]
            ]
            save_tuning_parameter_rows(self.selected_log_filename, self.tube_id, self.job_id, p1, initial_p2, p2)
            logger.info("튜닝 결과 저장 완료")


        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        font = QFont("Segoe UI", 10)
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setFont(font)

                if col_idx == len(row) - 1:
                    item.setForeground(QColor("#cc0000"))
                    item.setFont(QFont("Segoe UI", 10, italic=True, weight=QFont.Bold))
                    if row_idx != 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
                elif col_idx != 0:
                    try:
                        if int(value) != 0:
                            item.setBackground(QColor("#ccffcc"))
                            item.setForeground(QColor("#000000"))
                    except ValueError:
                        pass

                self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()
        logger.info("테이블 결과 렌더링 완료")
        
        self.classified_tuning_data = None

    def handle_header_click(self, index):
        zone_name = self.table.horizontalHeaderItem(index).text()
        if zone_name.startswith("Zone"):
            self.plot_zone(zone_name.upper())

    def plot_zone(self, zone_key):
        if zone_key not in self.zone_data:
            logger.warning(f"존 데이터 없음: {zone_key}")
            return

        x, sp, spike, profile = self.zone_data[zone_key]
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor="#2b2b2b")
        ax.plot(x, sp, label="SP")
        ax.plot(x, spike, label="Spike")
        ax.plot(x, profile, label="Profile")
        ax.set_title(zone_key, color="white")
        ax.set_xlabel("Time", color="white")
        ax.set_ylabel("Temp (\u00b0C)", color="white")
        ax.tick_params(colors="white")
        ax.grid(True, color="gray")
        ax.legend()
        self.canvas.draw()
        logger.debug(f"그래프 표시 완료: {zone_key}")