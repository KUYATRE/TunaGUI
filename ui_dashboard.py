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

        self.theta_plot_canvas = ThetaPlotCanvas()

        layout.addLayout(ip_layout)
        layout.addLayout(path_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.theta_plot_canvas)

        self.dual_regression_canvas = DualRegressionCanvas()
        layout.addWidget(self.dual_regression_canvas)

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

            X1, y1, X2, y2, intercept_time, coef_time, intercept_temp, coef_temp = regressor(filtered_df, zone_number)
            self.theta_plot_canvas.plot_text(
                "Step Time", intercept_time, coef_time,
                "SetPoint", intercept_temp, coef_temp
            )
            self.dual_regression_canvas.plot_dual_regression(X1, y1, intercept_time, coef_time, X2, y2, intercept_temp,
                                                             coef_temp)

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

    def display_theta_values(self, X, y, intercept, coef):
        coef_strs = []

        # DRIN_ZONE만 포함된 입력 컬럼만 필터링
        X_columns = pd.DataFrame(X).columns.tolist()

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

    def plot_dual_regression(self, X1, y1, intercept1, coef1, X2=None, y2=None, intercept2=None, coef2=None):
        self.ax1.clear()
        self.ax2.clear()
        self.ax1.set_facecolor('#1e1e1e')
        self.ax2.set_facecolor('#1e1e1e')

        # 첫 번째 회귀 결과 그리기
        x_vals1 = X1.iloc[:, 0].values
        y_vals1 = y1.values.flatten()
        self.ax1.scatter(x_vals1, y_vals1, color='deepskyblue', edgecolors='white')
        x_line1 = np.linspace(x_vals1.min(), x_vals1.max(), 100)
        y_line1 = intercept1 + coef1[0] * x_line1
        self.ax1.plot(x_line1, y_line1, color='deeppink', linewidth=2)
        self.ax1.set_title(f'{X1.columns[0]} vs y', color='white')
        self.ax1.set_xlabel(X1.columns[0], color='white')
        self.ax1.set_ylabel('y', color='white')
        self.ax1.tick_params(colors='white')

        # 두 번째 회귀 결과가 주어진 경우 그리기
        if X2 is not None and y2 is not None and intercept2 is not None and coef2 is not None:
            x_vals2 = X2.iloc[:, 0].values
            y_vals2 = y2.values.flatten()
            self.ax2.scatter(x_vals2, y_vals2, color='deepskyblue', edgecolors='white')
            x_line2 = np.linspace(x_vals2.min(), x_vals2.max(), 100)
            y_line2 = intercept2 + coef2[0] * x_line2
            self.ax2.plot(x_line2, y_line2, color='deeppink', linewidth=2)
            self.ax2.set_title(f'{X2.columns[0]} vs y', color='white')
            self.ax2.set_xlabel(X2.columns[0], color='white')
            self.ax2.set_ylabel('y', color='white')
            self.ax2.tick_params(colors='white')

        self.fig.tight_layout()
        self.draw()


class ThetaPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

    def plot_text(self, title1, intercept1, coef1, title2, intercept2, coef2):
        self.ax.clear()
        self.ax.axis('off')

        lines = []
        lines.append(f'[{title1}]')
        lines.append(f'절편: {float(intercept1):.6f}')
        for i, val in enumerate(np.ravel(coef1)):
            lines.append(f'계수{i + 1}: {float(val):.6f}')

        lines.append('')
        lines.append(f'[{title2}]')
        lines.append(f'절편: {float(intercept2):.6f}')
        for i, val in enumerate(np.ravel(coef2)):
            lines.append(f'계수{i + 1}: {float(val):.6f}')

        full_text = '\n'.join(lines)
        self.ax.text(0.01, 0.99, full_text, ha='left', va='top', fontsize=16, wrap=True, transform=self.ax.transAxes)
        self.draw()