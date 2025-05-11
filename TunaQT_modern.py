import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
    QComboBox, QTableWidget, QTableWidgetItem, QHBoxLayout, QFormLayout, QGroupBox, QSizePolicy
)
from PySide6.QtGui import QColor, QFont, QPalette, QIcon
from PySide6.QtCore import Qt, QSize
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from logAnalyser import get_file, detect_heater_zones, consol_controller, extract_all_zones_all_series_limited


class TunaAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TunaGUI")
        self.setGeometry(100, 100, 1000, 900)
        self.data_rows = []
        self.zone_data = {}
        self.selected_temp_mode = "normal"
        self.selected_etype = "BCl3"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # CSV 업로드 필드 (아이콘 제외, 라벨만 테두리 감싸기)
        file_layout = QHBoxLayout()

        self.upload_btn = QPushButton()
        self.upload_btn.setIcon(QIcon("disk_icon_purple.png"))
        self.upload_btn.setIconSize(QSize(36, 36))
        self.upload_btn.setFixedSize(40, 40)
        self.upload_btn.clicked.connect(self.load_csv)

        file_label_group = QGroupBox()
        file_label_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #5e35b1;
                border-radius: 8px;
                margin-top: 4px;
                padding: 8px;
            }
        """)
        file_label_layout = QVBoxLayout()

        self.file_label = QLabel("선택된 파일 없음")
        self.file_label.setStyleSheet("color: red; font-style: italic; font-weight: bold;")
        file_label_layout.addWidget(self.file_label)
        file_label_group.setLayout(file_label_layout)

        # 설정 필드와 동일한 폭으로 맞추기
        file_label_group.setMinimumWidth(400)
        file_label_group.setSizePolicy(file_label_group.sizePolicy().horizontalPolicy(), file_label_group.sizePolicy().verticalPolicy())

        file_layout.addWidget(self.upload_btn)
        file_layout.addWidget(file_label_group)

        # 설정 필드 (톱니바퀴 + 드롭다운 + 테두리 + 분석 버튼)
        settings_container = QHBoxLayout()

        gear_icon_label = QLabel()
        gear_icon_label.setPixmap(QIcon("gear_icon_purple.png").pixmap(36, 36))
        gear_icon_label.setFixedSize(40, 40)
        settings_container.addWidget(gear_icon_label)

        settings_group = QGroupBox()
        settings_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #5e35b1;
                border-radius: 8px;
                margin-top: 4px;
                padding: 8px;
            }
        """)
        settings_layout = QFormLayout()

        self.temp_mode_combo = QComboBox()
        self.temp_mode_combo.addItems(["normal", "high"])
        self.temp_mode_combo.currentTextChanged.connect(lambda text: setattr(self, "selected_temp_mode", text))

        self.etype_combo = QComboBox()
        self.etype_combo.addItems(["BCl3", "Annealing", "POCl3", "Oxidation"])
        self.etype_combo.currentTextChanged.connect(lambda text: setattr(self, "selected_etype", text))

        settings_layout.addRow("Temp Control Mode 선택", self.temp_mode_combo)
        settings_layout.addRow("설비군 선택", self.etype_combo)
        settings_group.setLayout(settings_layout)

        settings_container.addWidget(settings_group)

        # 분석 버튼을 설정 필드 오른쪽에 맞춤 높이로 배치
        self.analyze_btn = QPushButton("분석 실행")
        self.analyze_btn.setStyleSheet("background-color: #; color: white; border-radius: 4px; min-width: 300px;")
        self.analyze_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.analyze_btn.clicked.connect(self.run_analysis)
        settings_container.addWidget(self.analyze_btn)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: green; font-style: italic; border: 2px solid #5e35b1; border-radius: 8px; padding: 4px;")

        self.table = QTableWidget()
        self.table.setStyleSheet("font-family: 'Segoe UI'; font-size: 13px;")
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_click)

        self.figure = Figure(facecolor="#2b2b2b")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: #2b2b2b;")

        # 전체 레이아웃 정리
        layout.addLayout(file_layout)
        layout.addLayout(settings_container)
        layout.addWidget(self.result_label)
        layout.addWidget(self.table)
        layout.addWidget(self.canvas)

    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", "", "CSV files (*.csv)")
        if file_path:
            self.data_rows = get_file(file_path)
            self.file_label.setText(file_path)
            self.file_label.setStyleSheet("color: #00cc00; font-style: italic; font-weight: bold;")

    def run_analysis(self):
        if not self.data_rows:
            self.result_label.setText("CSV 파일을 먼저 업로드하세요.")
            return

        zone_count = detect_heater_zones(self.data_rows[0])
        headers = ["구분"] + [f"Zone{i+1}" for i in range(zone_count)] + ["비고"]

        p1, initial_p2, p2, recipe_step = consol_controller(
            self.selected_temp_mode, self.selected_etype, self.data_rows)
        self.zone_data = extract_all_zones_all_series_limited(self.data_rows, recipe_step)

        self.result_label.setText("분석 완료! (Zone 헤더 클릭으로 그래프 확인 가능)")

        rows = [
            ["초기 P2"] + initial_p2 + ["※ 첫 튜닝시에 적용"],
            ["P1 조정"] + p1 + [""],
            ["P2 조정"] + p2 + [""]
        ]

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

    def handle_header_click(self, index):
        zone_name = self.table.horizontalHeaderItem(index).text()
        if zone_name.startswith("Zone"):
            self.plot_zone(zone_name.upper())

    def plot_zone(self, zone_key):
        if zone_key not in self.zone_data:
            print("존 없음:", zone_key)
            return

        x, sp, spike, profile = self.zone_data[zone_key]
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor="#2b2b2b")
        ax.plot(x, sp, label="SP")
        ax.plot(x, spike, label="Spike")
        ax.plot(x, profile, label="Profile")
        ax.set_title(zone_key, color="white")
        ax.set_xlabel("Time", color="white")
        ax.set_ylabel("Temp (°C)", color="white")
        ax.tick_params(colors="white")
        ax.grid(True, color="gray")
        ax.legend()
        self.canvas.draw()


def set_dark_palette(app):
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.black)
    app.setPalette(dark_palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    set_dark_palette(app)
    window = TunaAnalyzer()
    window.show()
    try:
        sys.exit(app.exec())
    except SystemExit:
        print("종료 완료")
