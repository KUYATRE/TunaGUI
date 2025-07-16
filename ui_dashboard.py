from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QFrame, QTableWidget, QTableWidgetItem, QComboBox, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QThreadPool, QSettings
from algo_fins_comm import FinsUDPClient
from algo_fins_checkconnection import CheckConnectionWorker
from algo_prcess_data_refiner import DataProcessor
from algo_scikit_learn import regressor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import glob

import matplotlib
matplotlib.rcParams['font.family'] = 'Malgun Gothic'  # Windows: 맑은 고딕 사용
matplotlib.rcParams['axes.unicode_minus'] = False     # 음수 기호 깨짐 방지



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

        self.prev_trigger_bit = 0
        self.trigger_timer = QTimer()
        self.trigger_timer.timeout.connect(lambda: self.check_trigger_bit(0xA0, 0, 3))
        self.trigger_bit_val = 0

        self.trigger_mem_area = 0xA0
        self.trigger_mem_word = 0
        self.trigger_mem_bit = 3

        self.settings = QSettings("Diffusion", r"TunaGUI\ui_dashboard")

        self.selected_zone_number = 1

        self.df_plot = None
        self.theta0 = 0
        self.theta1 = 0
        self.theta2 = 0

        self.init_ui()

    def save_path_to_settings(self, new_path):
        self.settings.setValue("data_path", new_path)

    def save_ip_to_settings(self, new_ip):
        self.settings.setValue("ip_address", new_ip)

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
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_area.setWidget(self.scroll_content)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)

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
        row2.addWidget(self.read_data_lamp_label)
        row2.addWidget(self.read_data_lamp_text_label)
        row2.addWidget(self.hb_plc_lamp_label)
        row2.addWidget(self.hb_plc_lamp_text_label)

        status_layout = QVBoxLayout()
        status_layout.addLayout(row1)
        status_layout.addLayout(row2)

        status_group.setLayout(status_layout)
        self.scroll_layout.addWidget(status_group, alignment=Qt.AlignRight)

    def init_status_lamps(self):
        self.comm_lamp_label = QLabel()
        self.comm_lamp_label.setFixedSize(20, 20)
        self.comm_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.hb_pc_lamp_label = QLabel()
        self.hb_pc_lamp_label.setFixedSize(20, 20)
        self.hb_pc_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.read_data_lamp_label = QLabel()
        self.read_data_lamp_label.setFixedSize(20, 20)
        self.read_data_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

        self.hb_plc_lamp_label = QLabel()
        self.hb_plc_lamp_label.setFixedSize(20, 20)
        self.hb_plc_lamp_label.setStyleSheet("background-color: lightgray; border-radius: 10px;")

    def init_status_labels(self):
        self.comm_lamp_text_label = QLabel("통신 안 됨")
        self.comm_lamp_text_label.setStyleSheet("color: Red; font-weight: bold;")

        self.hb_pc_lamp_text_label = QLabel("Heartbeat(PC)")
        self.read_data_lamp_text_label = QLabel("Read data flag")
        self.hb_plc_lamp_text_label = QLabel("Heartbeat(PLC)")

        for lbl in [self.hb_pc_lamp_text_label, self.read_data_lamp_text_label, self.hb_plc_lamp_text_label]:
            lbl.setStyleSheet("font-weight: bold;")

    def add_horizontal_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        self.scroll_layout.addWidget(line)

    def add_main_connection_area(self):
        main_split_layout = QHBoxLayout()
        left = self.create_left_connection_layout()
        vline = self.create_vertical_separator()
        right = self.create_right_placeholder_layout()

        main_split_layout.addLayout(left)
        main_split_layout.addWidget(vline)
        main_split_layout.addLayout(right)

        self.scroll_layout.addLayout(main_split_layout)

    def create_left_connection_layout(self):
        layout = QVBoxLayout()

        ip_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        saved_ip = self.settings.value("ip_address", r"172.22.80.1")
        self.ip_input.setText(saved_ip)
        self.ip_input.textChanged.connect(self.save_ip_to_settings)

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

        # === 경로 입력 행 추가 ===
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        saved_path = self.settings.value("data_path", r"C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets")
        self.path_input.setText(saved_path)
        self.path_input.textChanged.connect(self.save_path_to_settings)

        path_layout.addWidget(QLabel("로그 경로 : "))
        path_layout.addWidget(self.path_input)

        # === 세타 값 표시용 QLabel 추가 ===
        self.theta_display_label = QLabel("회귀 결과 대기 중...")
        self.theta_display_label.setAlignment(Qt.AlignLeft)
        self.theta_display_label.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")

        layout.addLayout(ip_layout)
        layout.addLayout(path_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.theta_display_label)

        # === 세타 시각화 코드 추가 ===
        # self.theta_plot_canvas = ThetaPlotCanvas()
        # layout.addWidget(self.theta_plot_canvas)
        #
        # self.regression_canvas = RegressionLineCanvas()
        # layout.addWidget(self.regression_canvas)
        #
        # self.dual_regression_canvas = DualRegressionCanvas()
        # layout.addWidget(self.dual_regression_canvas)
        path_temp = r'C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets\MERGE_dummy_data.csv'
        try:
            print(f"[DEBUG] 파일 로딩 시도: {path_temp}")
            df = pd.read_csv(path_temp)
            print(f"[DEBUG] 컬럼 목록: {df.columns.tolist()}")

            step_col = next((c for c in df.columns if 'step' in c.lower() and 'time' in c.lower()), None)
            zone_col = next((c for c in df.columns if f'zone{self.selected_zone_number}' in c.lower() and 'sp' in c.lower()),
                            None)

            print(f"[DEBUG] 탐색된 step_col: {step_col}, zone_col: {zone_col}")

            if step_col and zone_col:
                df[f'RS_ZONE{self.selected_zone_number}'] = 0.4 * df[step_col] + 0.2 * df[zone_col] + 50
                self.df_plot = df
                self.theta0 = 50
                self.theta1 = 0.4
                self.theta2 = 0.2
                print(f"[DEBUG] 회귀 입력 생성 완료 → step='{step_col}', zone='{zone_col}'")
            else:
                print("[ERROR] 유사한 step/zone 컬럼을 찾을 수 없습니다.")
                self.df_plot = None
        except Exception as e:
            print(f"[ERROR] MERGE 파일 로딩 실패: {e}")
            self.df_plot = None

        if self.df_plot is not None:
            print("[DEBUG] df_plot 성공적으로 생성됨, 위젯 추가 시도")
            widget = FixedRegressionPlotWidget(self.df_plot, self.theta0, self.theta1, self.theta2, self.selected_zone_number)
            layout.addWidget(widget)
        else:
            print("[DEBUG] df_plot이 None 상태, 회귀 시각화 불가")
            layout.addWidget(QLabel("회귀 시각화 불가: 데이터가 없거나 컬럼이 누락되었습니다."))

        return layout

    def create_vertical_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def create_right_placeholder_layout(self):
        self.right_layout = QVBoxLayout()

        self.zone_combo = QComboBox()
        self.zone_combo.addItems([f"ZONE{i}" for i in range(1, 9)])
        self.zone_combo.currentIndexChanged.connect(self.zone_selection_changed)
        self.right_layout.addWidget(self.zone_combo)

        self.table_widget = QTableWidget()
        self.right_layout.addWidget(self.table_widget)

        self.load_csv_button = QPushButton("최신 MERGE CSV 불러오기")
        self.load_csv_button.clicked.connect(
            lambda: self.load_latest_merge_csv_and_display(self.path_input.text().strip(), self.selected_zone_number))
        self.right_layout.addWidget(self.load_csv_button)

        return self.right_layout

    def zone_selection_changed(self, index):
        self.selected_zone_number = index + 1
        self.load_latest_merge_csv_and_display(self.path_input.text().strip(), self.selected_zone_number)

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
            self.trigger_timer.start(300)

            self.disconnect_btn.setEnabled(True)
            self.connect_btn.setEnabled(False)

            # try_connect() 끝부분에 추가
            self.load_latest_merge_csv_and_display(self.path_input.text().strip())


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

    def check_trigger_bit(self, mem_area, word_addr, bit_offset):
        try:
            self.trigger_bit_val = self.fins.read_word_bit(mem_area=mem_area, word_addr=word_addr, bit_offset=bit_offset)
            print(self.prev_trigger_bit, self.trigger_bit_val)
            if self.prev_trigger_bit == 0 and self.trigger_bit_val == 1:
                print("트리거 비트 상승 감지")
                self.update_data_read_lamp(True)
                self.read_data()

            self.prev_trigger_bit = self.trigger_bit_val
            if self.prev_trigger_bit == 0:
                self.update_data_read_lamp(False)

        except Exception as e:
            print("트리거 비트 읽기 오류: ", e)

    def read_data(self):
        save_dir = self.path_input.text().strip()
        self.processor = DataProcessor(save_dir)

        result = self.processor.data_receive(
            self.ip_input.text().strip(),
            self.plc_port,
            self.plc_node,
            self.pc_node,
            self.trigger_bit_val
        )
        print(result)
        if result:
            tube_id, job_id, sheet_res_data = result
            self.processor.load_csv_to_dataframe()
            self.processor.strip_process_dataframe()
            self.processor.strip_sheet_res_dataframe(tube_id, job_id, sheet_res_data)
            self.processor.merge_two_csv(tube_id, job_id)

            return None
        else:
            return None

    def load_latest_merge_csv_and_display(self, base_dir: str, zone_number: int = 1):
        try:
            search_pattern = os.path.join(base_dir, "**", "*MERGE*.csv")
            matched_files = glob.glob(search_pattern, recursive=True)

            if not matched_files:
                print("MERGE 파일을 찾을 수 없습니다.")
                return

            latest_file = max(matched_files, key=os.path.getmtime)
            print(f"최신 MERGE 파일 경로: {latest_file}")

            df = pd.read_csv(latest_file)
            df.columns = [col.strip() for col in df.columns]

            common_cols = ['RS_Tube ID', 'RS_JobNo', 'DRIN_Step Name', 'DRIN_Step Time']
            zone_cols1 = [col for col in df.columns if col.startswith(f'RS_ZONE{zone_number}')]
            zone_cols2 = [col for col in df.columns if col.startswith(f'DRIN_ZONE{zone_number}')]
            filtered_cols = common_cols + zone_cols1 + zone_cols2

            filtered_df = df[filtered_cols]
            self.display_dataframe(filtered_df)

            intercept, coef = regressor(filtered_df, zone_number)
            self.display_theta_values(zone_number, intercept, coef, filtered_df)

        except Exception as e:
            print(f"MERGE CSV 불러오기 오류: {e}")

    def display_dataframe(self, df: pd.DataFrame):
        if not hasattr(self, 'table_widget'):
            self.table_widget = QTableWidget()
            self.right_layout.addWidget(self.table_widget)

        self.table_widget.clear()
        self.table_widget.setRowCount(len(df))
        self.table_widget.setColumnCount(len(df.columns))
        self.table_widget.setHorizontalHeaderLabels(df.columns.astype(str).tolist())

        for i in range(len(df)):
            for j in range(len(df.columns)):
                item = QTableWidgetItem(str(df.iat[i, j]))
                self.table_widget.setItem(i, j, item)

        self.table_widget.resizeColumnsToContents()

    def display_theta_values(self, zone, intercept, coef, df):
        coef_strs = []

        # DRIN_ZONE만 포함된 입력 컬럼만 필터링
        X_columns1 = df.columns[df.columns.str.contains(fr'DRIN_ZONE{zone}\(SP\)', case=False)]
        X_columns2 = df.columns[df.columns.str.contains(f'DRIN_Step Time', case=False)]
        X_columns = X_columns1.union(X_columns2)

        # 디버그 출력
        print(f"[디버그] X 컬럼 수: {len(X_columns)}, 계수 수: {len(coef)}")
        print(f"[디버그] X 컬럼 이름: {list(X_columns)}")
        print(f"[디버그] coef 원본: {coef}")

        # 다차원 계수 배열 평탄화
        if hasattr(coef, 'shape') and len(coef.shape) > 1:
            coef = coef.ravel()

        # 컬럼 수와 계수 수 일치 여부 확인
        if len(X_columns) == len(coef):
            for col, val in zip(X_columns, coef):
                coef_strs.append(f"{col}: {float(val):.6f}")
        else:
            coef_strs.append("[계수 수와 컬럼 수 불일치]")

        coef_text = "\n".join(coef_strs)

        # intercept 처리
        if hasattr(intercept, '__iter__') and not isinstance(intercept, str):
            intercept_val = float(intercept[0])
        else:
            intercept_val = float(intercept)

        print(f"계수 출력: {coef_text}")

        self.theta_display_label.setText(
            f"절편 (Intercept): {intercept_val:.6f}\n\n계수 (Coefficients):\n{coef_text}"
        )

        # === y 생성 후 그래프 표시 ===
        y_cols = df.columns[df.columns.str.contains(f'RS_ZONE{zone}', case=False)]
        if not y_cols.empty:
            y = df[y_cols].iloc[:, 0]
            X = df[X_columns]
            if hasattr(self, 'theta_plot_canvas'):
                self.theta_plot_canvas.plot_distribution(y.values, intercept_val)

        if hasattr(self, 'regression_canvas') and len(X_columns) > 0:
            x_input = df[X_columns]
            y_target = df[y_cols].iloc[:, 0]
            self.regression_canvas.plot_regression(x_input, y_target, intercept_val, coef)

        if hasattr(self, 'dual_regression_canvas'):
            self.dual_regression_canvas.plot_dual_regression(X, y, intercept, coef)

        self.df_plot = X_columns.union(y_cols)
        self.theta0 = intercept_val
        self.theta1 = coef[0]
        self.theta2 = coef[1]


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

    def update_data_read_lamp(self, is_alive):
        color = "#A8E6CF" if is_alive else "lightgray"
        self.read_data_lamp_label.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
        self.read_data_lamp_text_label.setText("Read data flag")
        self.read_data_lamp_text_label.setStyleSheet("color: black; font-weight: bold;")

    def update_plc_hb_lamp(self, is_alive):
        color = "#A8E6CF" if is_alive else "lightgray"
        self.hb_plc_lamp_label.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
        self.hb_plc_lamp_text_label.setText("Heartbeat(PLC)")
        self.hb_plc_lamp_text_label.setStyleSheet("color: black; font-weight: bold;")

class ThetaPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.plot_reference_done = False

    def plot_distribution(self, y, intercept):
        self.ax.clear()

        # NaN 및 이상치 제거
        y = np.array(y)
        y = y[np.isfinite(y)]

        if len(y) == 0:
            self.ax.text(0.5, 0.5, "데이터 없음", ha='center', va='center', transform=self.ax.transAxes)
            self.draw()
            return

        self.ax.hist(y, bins=30, alpha=0.6, color='skyblue', edgecolor='black')
        self.ax.axvline(intercept, color='red', linestyle='--', label=f'Intercept: {intercept:.2f}')

        # X축 확대 여유
        min_y, max_y = y.min(), y.max()
        margin = (max_y - min_y) * 0.1 if max_y != min_y else 1
        self.ax.set_xlim(min_y - margin, max_y + margin)

        self.ax.set_title("목표 변수 분포 및 절편")
        self.ax.set_xlabel("y 값")
        self.ax.set_ylabel("빈도")
        self.ax.legend()
        self.fig.tight_layout()
        self.draw()


class RegressionLineCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#1e1e1e')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setStyleSheet("background-color: #1e1e1e;")

    def plot_regression(self, X, y, intercept, coef):
        self.ax.clear()
        self.ax.set_facecolor('#1e1e1e')

        # 산점도: 첫 번째 입력 변수만 사용
        x_vals = X.iloc[:, 0].values
        y_vals = y.values
        self.ax.scatter(x_vals, y_vals, color='deepskyblue', edgecolors='white')

        # 회귀선 그리기
        x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
        y_line = intercept + coef[0] * x_line
        self.ax.plot(x_line, y_line, color='deeppink', linewidth=2)

        self.ax.set_title(r'$h_\theta(x) = \theta_0 + \theta_1 x$', fontsize=14, color='white')
        self.ax.set_xlabel('입력 변수', color='white')
        self.ax.set_ylabel('목표 변수', color='white')
        self.ax.tick_params(colors='white')
        self.fig.tight_layout()
        self.draw()


class DualRegressionCanvas(FigureCanvas):
    def __init__(self, parent=None, width=10, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#1e1e1e')
        self.ax1 = self.fig.add_subplot(1, 2, 1)
        self.ax2 = self.fig.add_subplot(1, 2, 2)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setStyleSheet("background-color: #1e1e1e;")

    def plot_dual_regression(self, X, y, intercept, coef):
        x1 = X.iloc[:, 0].values
        x2 = X.iloc[:, 1].values
        y_vals = y.values

        self.ax1.clear()
        self.ax2.clear()
        self.ax1.set_facecolor('#1e1e1e')
        self.ax2.set_facecolor('#1e1e1e')

        # 첫 번째 입력 변수에 대한 회귀선
        self.ax1.scatter(x1, y_vals, color='deepskyblue', edgecolors='white')
        x1_line = np.linspace(x1.min(), x1.max(), 100)
        y1_line = intercept + coef[0] * x1_line
        self.ax1.plot(x1_line, y1_line, color='deeppink', linewidth=2)
        self.ax1.set_title(f'{X.columns[0]} vs y', color='white')
        self.ax1.set_xlabel(X.columns[0], color='white')
        self.ax1.set_ylabel('y', color='white')
        self.ax1.tick_params(colors='white')

        # 두 번째 입력 변수에 대한 회귀선
        self.ax2.scatter(x2, y_vals, color='deepskyblue', edgecolors='white')
        x2_line = np.linspace(x2.min(), x2.max(), 100)
        y2_line = intercept + coef[1] * x2_line
        self.ax2.plot(x2_line, y2_line, color='deeppink', linewidth=2)
        self.ax2.set_title(f'{X.columns[1]} vs y', color='white')
        self.ax2.set_xlabel(X.columns[1], color='white')
        self.ax2.set_ylabel('y', color='white')
        self.ax2.tick_params(colors='white')

        self.fig.tight_layout()
        self.draw()


class FixedRegressionPlotWidget(QWidget):
    def __init__(self, df, theta0, theta1, theta2, selected_zone=None, parent=None):
        super().__init__(parent)
        self.df = df
        self.theta0 = theta0
        self.theta1 = theta1
        self.theta2 = theta2
        self.selected_zone = selected_zone if selected_zone is not None else 1  # fallback 처리
        print(f"[DEBUG] FixedRegressionPlotWidget 초기화 - selected_zone: {self.selected_zone}")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 컬럼 후보 여러 개 지정하여 유연하게 매칭
        zone_col_candidates = [
            f"DRIN_ZONE{self.selected_zone}(SP)",
            f"DRIN_ZONE{self.selected_zone}_SP",
            f"DRIN_ZONE{self.selected_zone}"
        ]

        zone_col = next((col for col in zone_col_candidates if col in self.df.columns), None)

        print(f"[DEBUG] 사용 가능한 zone 컬럼 후보: {zone_col_candidates}")
        print(f"[DEBUG] 선택된 zone_col: {zone_col}")

        if (
            self.df is not None and
            'DRIN_Step Time' in self.df.columns and
            zone_col is not None and
            'y' in self.df.columns
        ):
            fig = self.plot_regression(zone_col)
            canvas = FigureCanvas(fig)
            layout.addWidget(canvas)
        else:
            print("[ERROR] 회귀 시각화 실패 - 컬럼 확인 필요")
            layout.addWidget(QLabel("회귀 시각화 불가: 필요한 컬럼이 없습니다."))

    def plot_regression(self, zone_col):
        x1 = self.df['DRIN_Step Time'].values
        x2 = self.df[zone_col].values
        y = self.df['y'].values

        y_pred = self.theta0 + self.theta1 * x1 + self.theta2 * x2

        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(x1, x2, y, color='deepskyblue', edgecolor='white', label='Actual')

        x1_grid, x2_grid = np.meshgrid(
            np.linspace(x1.min(), x1.max(), 20),
            np.linspace(x2.min(), x2.max(), 20)
        )
        y_grid = self.theta0 + self.theta1 * x1_grid + self.theta2 * x2_grid

        ax.plot_surface(x1_grid, x2_grid, y_grid, color='deeppink', alpha=0.6)
        ax.set_xlabel('DRIN_Step Time')
        ax.set_ylabel(zone_col)
        ax.set_zlabel('y')
        ax.set_title(f'y = θ₀ + θ₁ * Step + θ₂ * {zone_col}')
        return fig