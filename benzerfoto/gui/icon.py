"""Uygulama simgesi (BF logosu) ve Windows görev çubuğu kimliği."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from benzerfoto import __version__

# PyInstaller paketinde de aynı göreli konumda durur (benzerfoto.spec → datas)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_USER_MODEL_ID = f"BenzerFoto.BenzerFoto.{__version__}"


def app_icon() -> QIcon:
    """Her boyutu ayrı çizilmiş PNG'lerden simge: küçük boyutlarda da net görünür."""
    icon = QIcon()
    for size in ICON_SIZES:
        path = ASSETS_DIR / f"bf-{size}.png"
        if path.exists():
            icon.addFile(str(path))
    return icon


def set_windows_app_id() -> bool:
    """Windows'a uygulamanın kendi kimliğini bildirir.

    Bu yapılmazsa Windows, Python ile açılan uygulamayı "python.exe" sayar ve
    görev çubuğunda Python simgesini gösterir. QApplication'dan önce çağrılmalı.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        return True
    except (AttributeError, OSError):  # çok eski Windows: simge yine pencerede görünür
        return False
