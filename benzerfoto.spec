# -*- mode: python ; coding: utf-8 -*-
# BenzerFoto için PyInstaller paketleme tanımı (--onedir).
#
# Derleme:  .venv\Scripts\python -m PyInstaller --noconfirm benzerfoto.spec
# Çıktı:    dist\BenzerFoto\BenzerFoto.exe       (pencereli arayüz)
#           dist\BenzerFoto\benzerfoto-cli.exe   (konsol: scan, info, doctor kontrolü)
# İki EXE aynı klasördeki kütüphaneleri paylaşır.

import glob
import os
import sysconfig

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

site = sysconfig.get_paths()["purelib"]

# pillow-heif'in yerel kütüphanesi (libheif-*.dll) site-packages kökünde durur;
# bağımlılık taraması bulamazsa diye açıkça eklenir.
heif_binaries = [(p, ".") for p in glob.glob(os.path.join(site, "libheif*.dll"))]
heif_binaries += collect_dynamic_libs("pillow_heif")

# Kullanılmayan büyük Qt modülleri paketi şişirmesin
qt_excludes = [
    "PySide6." + m
    for m in (
        "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel", "QtWebSockets",
        "QtPdf", "QtPdfWidgets", "QtQml", "QtQuick", "QtQuickWidgets", "QtQuick3D", "Qt3DCore",
        "Qt3DRender", "QtMultimedia", "QtMultimediaWidgets", "QtCharts", "QtDataVisualization",
        "QtGraphs", "QtBluetooth", "QtPositioning", "QtLocation", "QtSensors", "QtSerialPort",
        "QtSql", "QtTest", "QtDesigner", "QtHelp", "QtOpenGL", "QtOpenGLWidgets", "QtSvgWidgets",
        "QtNetworkAuth", "QtRemoteObjects", "QtScxml", "QtSpatialAudio", "QtTextToSpeech",
    )
]

a = Analysis(
    ["benzerfoto/__main__.py"],
    pathex=["."],
    binaries=heif_binaries,
    datas=[],
    hiddenimports=collect_submodules("benzerfoto") + ["pillow_heif", "_pillow_heif"],
    excludes=qt_excludes + ["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BenzerFoto",
    console=False,
    upx=False,
)
cli_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="benzerfoto-cli",
    console=True,
    upx=False,
)
coll = COLLECT(
    gui_exe,
    cli_exe,
    a.binaries,
    a.datas,
    upx=False,
    name="BenzerFoto",
)
