"""Arayüzü başlatır."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from benzerfoto.gui.icon import app_icon, set_windows_app_id
from benzerfoto.gui.main_window import MainWindow
from benzerfoto.gui.style import apply_theme
from benzerfoto.paths import prepare_location


def copy_settings(source: QSettings, target: QSettings) -> int:
    """Bütün ayar anahtarlarını bir ayar deposundan diğerine kopyalar."""
    keys = source.allKeys()
    for key in keys:
        target.setValue(key, source.value(key))
    target.sync()
    return len(keys)


def open_settings(settings_file: Path | None) -> QSettings:
    """Ayar deposunu açar.

    Dosya verilmezse taşınabilir moddaki EXE program klasöründeki `veri\\ayarlar.ini`
    dosyasını kullanır; dosya ilk kez oluşturuluyorsa kayıt defterindeki eski ayarlar
    (klasör listesi, eşikler, pencere boyutu) içine kopyalanır. Kaynaktan çalışırken
    ayarlar eskisi gibi kayıt defterinde kalır.
    """
    if settings_file is None:
        location = prepare_location()
        if location.settings_file is None:
            return QSettings()
        settings_file = location.settings_file
        if not settings_file.exists():
            copy_settings(QSettings(), QSettings(str(settings_file), QSettings.Format.IniFormat))
    return QSettings(str(settings_file), QSettings.Format.IniFormat)


def run(db_path: Path | None = None, settings_file: Path | None = None) -> int:
    # QSettings bu adları kullanır: kayıt defterinde HKCU\Software\BenzerFoto\BenzerFoto
    QApplication.setApplicationName("BenzerFoto")
    QApplication.setOrganizationName("BenzerFoto")
    set_windows_app_id()  # görev çubuğunda Python değil BF simgesi görünsün
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    app.setWindowIcon(app_icon())
    window = MainWindow(db_path, open_settings(settings_file))
    window.show()
    if settings_file is None and prepare_location().portable:
        window.statusBar().showMessage(
            f"Taşınabilir mod: ayarlar ve önbellek {prepare_location().folder} klasöründe.", 10000
        )
    return app.exec()
