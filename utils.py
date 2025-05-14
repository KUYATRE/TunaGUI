# utils.py

from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

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
