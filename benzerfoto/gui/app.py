"""Arayüzü başlatır."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from benzerfoto.gui.main_window import MainWindow
from benzerfoto.gui.style import STYLESHEET


def run(db_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("BenzerFoto")
    app.setOrganizationName("BenzerFoto")
    app.setStyle("Fusion")  # her Windows sürümünde aynı görünüm
    app.setStyleSheet(STYLESHEET)
    window = MainWindow(db_path)
    window.show()
    return app.exec()
