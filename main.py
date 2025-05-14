# main.py – TunaGUI 실행 진입점

import sys
from PySide6.QtWidgets import QApplication
from ui_main_window import TunaAnalyzer
from ui_components import set_dark_palette

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
