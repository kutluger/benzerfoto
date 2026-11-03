"""Arayüzün açılıp tarama sonrası grupları gösterdiğini kontrol eden duman testi.

PySide6 ya da grafik kütüphaneleri yoksa atlanır.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from benzerfoto.cache import FeatureCache  # noqa: E402
from benzerfoto.grouping import GroupKind  # noqa: E402
from benzerfoto.scanner import scan  # noqa: E402
from tests.conftest import make_scene, save_jpeg  # noqa: E402


def ini_settings(tmp_path: Path):
    """Geçici INI dosyası: testler gerçek ayarlara (kayıt defteri) hiç dokunmaz."""
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "ayarlar.ini"), QSettings.Format.IniFormat)


@pytest.fixture(scope="module")
def app():
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.setOrganizationName("BenzerFotoTest")
    QCoreApplication.setApplicationName("BenzerFotoTest")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_window_shows_groups(app, tmp_path: Path):
    from PySide6.QtCore import QThreadPool

    from benzerfoto.gui.main_window import FOLDER_PROTECT, MainWindow

    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8, blur=2 if i == 1 else 0), root / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    with FeatureCache(tmp_path / "db.sqlite") as cache:
        features = scan([root], cache, workers=1).features

    w = MainWindow(tmp_path / "db.sqlite", ini_settings(tmp_path))
    w.features = features
    w._regroup_all()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()

    assert len(w.groups_by_kind[GroupKind.SCENE]) == 1
    assert w.current_group is not None
    assert len(w.grid.cards) == 3
    assert len(w.current_group.marked) == 2

    # İşareti kaldır, sonra "bunu tut" ile başka kareyi öner
    marked = sorted(w.current_group.marked)[0]
    w._on_mark_toggled(marked, False)
    assert marked not in w.current_group.marked
    w._keep_only(marked)
    assert w.current_group.best_path == marked
    assert len(w.current_group.marked) == 2

    # Koruma kuralı: klasör korunursa hiçbir dosya işaretli kalmaz
    w._append_folder(str(root), FOLDER_PROTECT)
    w._reapply_protection()
    assert w.current_group.marked == set()
    w.close()


def test_move_and_undo_updates_groups(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from benzerfoto import actions
    from benzerfoto.cache import FeatureCache as Cache
    from benzerfoto.gui.main_window import FOLDER_SCAN, MainWindow
    from benzerfoto.journal import KIND_MOVE

    # Bilgi pencereleri testi bekletmesin
    for name in ("information", "warning"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: None))

    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8, blur=2 if i == 1 else 0), root / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    db = tmp_path / "db.sqlite"
    with Cache(db) as cache:
        features = scan([root], cache, workers=1).features

    w = MainWindow(db, ini_settings(tmp_path))
    w._append_folder(str(root), FOLDER_SCAN)
    w.features = features
    w._regroup_all()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert not w.undo_button.isEnabled()
    assert w.move_button.isEnabled()

    paths, _size, skipped = w._collect_marked(w.groups_by_kind[GroupKind.SCENE])
    assert len(paths) == 2 and skipped == 0
    result = actions.move_to_duplicates(db, paths, w._folders(FOLDER_SCAN))
    w._on_action_done(KIND_MOVE, result)
    assert len(w.features) == 1
    assert w.groups_by_kind[GroupKind.SCENE] == []  # tek fotoğraf kaldı, grup kalmadı
    assert w.undo_button.isEnabled() and not w.move_button.isEnabled()
    assert len(list((root / "_benzerler").iterdir())) == 2

    undo = actions.undo(db, result.op_id)
    with Cache(db) as cache:
        feats = cache.get_features(undo.done)
    w._on_undo_done((undo, feats))
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert len(w.features) == 3
    assert len(w.groups_by_kind[GroupKind.SCENE]) == 1
    assert not w.undo_button.isEnabled()
    w.close()


def _window_with_group(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from benzerfoto.gui.main_window import MainWindow

    for name in ("information", "warning"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: 0)
    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8), root / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    db = tmp_path / "db.sqlite"
    with FeatureCache(db) as cache:
        features = scan([root], cache, workers=1).features
    w = MainWindow(db, ini_settings(tmp_path))
    assert not w.report_button.isEnabled()  # grup yokken rapor alınmaz
    w.features = features
    w._regroup_all()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    return w


def test_report_button_writes_files(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    w = _window_with_group(app, tmp_path, monkeypatch)
    assert w.report_button.isEnabled()
    for name in ("rapor.html", "rapor.csv"):
        out = tmp_path / name
        w.export_report_to(str(out))
        QThreadPool.globalInstance().waitForDone(10000)
        app.processEvents()
        assert out.exists() and out.stat().st_size > 0
    assert (tmp_path / "rapor.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert (tmp_path / "rapor.html").read_text(encoding="utf-8").count("base64,") == 3
    assert not w._busy and w.report_button.isEnabled()
    w.close()


def test_settings_apply_and_persist(app, tmp_path: Path, monkeypatch):
    from benzerfoto.gui.main_window import MainWindow
    from benzerfoto.settings import AppSettings

    w = _window_with_group(app, tmp_path, monkeypatch)
    w.apply_app_settings(AppSettings(similar_threshold=90, scene_threshold=95, scene_window=10, workers=2))
    assert w.thresholds[GroupKind.SCENE] == 95.0
    assert w.window_combo.currentData() == 10
    assert w.app_settings.effective_workers() == 2
    w.close()

    # Yeniden açılışta varsayılanlar okunur; oturumdaki kaydırıcı değeri değil
    w2 = MainWindow(tmp_path / "db.sqlite", ini_settings(tmp_path))
    assert w2.thresholds[GroupKind.SIMILAR] == 90.0
    assert w2.window_combo.currentData() == 10
    w2.threshold_slider.setValue(60)
    w2.close()
    w3 = MainWindow(tmp_path / "db.sqlite", ini_settings(tmp_path))
    assert w3.thresholds[GroupKind.SIMILAR] == 90.0
    w3.close()


def test_settings_dialog_values(app):
    from benzerfoto.gui.settings_dialog import SettingsDialog
    from benzerfoto.settings import AppSettings

    dlg = SettingsDialog(AppSettings(similar_threshold=85, scene_window=300, workers=4))
    assert dlg.values() == AppSettings(similar_threshold=85, scene_window=300, workers=4)
    dlg.set_values(AppSettings())
    assert dlg.values() == AppSettings()


def test_report_disabled_during_scan_and_failure_is_reported(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from benzerfoto import report

    w = _window_with_group(app, tmp_path, monkeypatch)
    # Tarama sürerken rapor alınmaz (DURDUR düğmesinin durumu bozulmasın)
    w.scan_thread = object()
    w._update_action_buttons()
    assert not w.report_button.isEnabled()
    w.export_report_to(str(tmp_path / "olmamali.html"))
    assert not w._busy and not (tmp_path / "olmamali.html").exists()
    w.scan_thread = None
    w._update_action_buttons()
    assert w.report_button.isEnabled()

    # Yazma hatası: kullanıcıya doğru ipucu gösterilir, arayüz kilitli kalmaz
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a[2])))
    monkeypatch.setattr(report, "write_report", lambda *a, **k: (_ for _ in ()).throw(OSError("erişim engellendi")))
    w.export_report_to(str(tmp_path / "rapor.html"))
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert shown and "Rapor kaydedilemedi" in shown[0]
    assert not w._busy and w.report_button.isEnabled()
    w.close()


def _mean_lightness(widget) -> float:
    img = widget.grab().toImage()
    values = [img.pixelColor(x, y).lightness() for x in range(0, img.width(), 3) for y in range(0, img.height(), 3)]
    return sum(values) / len(values)


def test_card_context_menu_is_readable(app):
    """Kart menüsü saydam (siyah kutu) değil, açık zeminli çizilir; tema açık kalır."""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QMenu

    from benzerfoto.gui.images import ThumbnailCache
    from benzerfoto.gui.style import apply_theme
    from benzerfoto.gui.widgets import ThumbnailGrid

    apply_theme(app)
    assert app.palette().color(QPalette.ColorRole.Window).lightness() > 200
    grid = ThumbnailGrid(ThumbnailCache())
    menu = QMenu(grid._container)  # kartlar bu kabın içinde durur
    menu.addAction("★ Bunu tut, diğerlerini işaretle")
    menu.addAction("📂 Dosya konumunu aç")
    menu.ensurePolished()
    menu.adjustSize()
    assert _mean_lightness(menu) > 200


def test_app_icon_and_ico_sizes(app):
    """BF logosu: pencere simgesi tüm boyutlarda yüklü, ICO 16-256 px içerir."""
    import sys

    from PIL import Image

    from benzerfoto.gui.icon import ASSETS_DIR, ICON_SIZES, app_icon, set_windows_app_id

    icon = app_icon()
    assert not icon.isNull()
    assert {s.width() for s in icon.availableSizes()} >= set(ICON_SIZES)
    with Image.open(ASSETS_DIR / "bf.ico") as ico:
        sizes = {w for w, _h in ico.info["sizes"]}
    assert {16, 32, 48, 256} <= sizes
    assert set_windows_app_id() == (sys.platform == "win32")
