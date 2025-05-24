# TunaGUI Main Entry (통합된 GUI를 메뉴바 구조로 관리)
# 페이지별 GUI 클래스는 ui_tuning.py, ui_dashboard.py 로 분리됨

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QStackedWidget, QWidget

# 외부 페이지 클래스 import
from ui_tuning import TuningPage
from ui_dashboard import SettingsPage

class TunaAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TunaGUI")
        self.setGeometry(100, 100, 1200, 900)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # === 사이드바 ===
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: lightgray; border-right: 2px solid #5e35b1;")

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(10, 10, 10, 10)

        menu_tuning = QPushButton("Tuning")
        menu_dashboard = QPushButton("Dashboard")
        sidebar_layout.addWidget(menu_dashboard)
        sidebar_layout.addWidget(menu_tuning)
        sidebar_layout.addStretch()
        self.sidebar.setLayout(sidebar_layout)

        self.sidebar.setVisible(False)

        # 햄버거 토글 버튼
        self.toggle_btn = QPushButton("≡")
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setStyleSheet("background-color: #5e35b1; color: white; font-size: 20px")
        self.toggle_btn.clicked.connect(self.toggle_sidebar)

        # === 페이지 관리 ===
        self.page_tunner = TuningPage()
        self.page_settings = SettingsPage()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.page_tunner)     # index 0
        self.stacked_widget.addWidget(self.page_settings)   # index 1

        # 페이지 전환 이벤트 연결
        menu_tuning.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        menu_dashboard.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        # 사이드바 + 페이지 결합
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.toggle_btn)
        left_layout.addWidget(self.sidebar)

        sidebar_container = QWidget()
        sidebar_container.setLayout(left_layout)

        main_layout.addWidget(sidebar_container)
        main_layout.addWidget(self.stacked_widget)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

# 실행 엔트리 포인트
# 실행 엔트리 포인트는 main.py로 이동되었습니다.
# 이 파일은 TunaAnalyzer 클래스 정의만 포함합니다.