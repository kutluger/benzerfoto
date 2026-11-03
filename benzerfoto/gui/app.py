"""Arayüzü başlatır."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from benzerfoto.gui.main_window import MainWindow
from benzerfoto.gui.style import STYLESHEET


def run(db_path: Path | None = None, settings_file: Path | None = None) -> int:
    # QSettings bu adları kullanır: ayarlar HKCU\Software\BenzerFoto\BenzerFoto altında
    QApplication.setApplicationName("BenzerFoto")
    QApplication.setOrganizationName("BenzerFoto")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")  # her Windows sürümünde aynı görünüm
    app.setStyleSheet(STYLESHEET)
    settings = QSettings(str(settings_file), QSettings.Format.IniFormat) if settings_file else None
    window = MainWindow(db_path, settings)
    window.show()
    return app.exec()
