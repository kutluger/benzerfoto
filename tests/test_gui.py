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


def _window_with_two_groups(app, tmp_path: Path, monkeypatch):
    """İki ayrı sahne grubu (biri 3, biri 2 fotoğraf) olan pencere."""
    from PySide6.QtCore import QThreadPool

    from benzerfoto.gui.main_window import MainWindow

    for name in ("information", "warning"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: None))
    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8), root / f"A_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    for i in range(2):
        save_jpeg(make_scene(7, shift=i * 8), root / f"B_{i}.jpg", f"2025:09:01 10:00:{10 + i * 5:02}")
    db = tmp_path / "db.sqlite"
    with FeatureCache(db) as cache:
        features = scan([root], cache, workers=1).features
    w = MainWindow(db, ini_settings(tmp_path))
    w.features = features
    w._regroup_all()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert len(w.visible_groups) == 2
    return w


def test_keyboard_navigation(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    w.show()
    first, second = w.visible_groups

    # Page Down / Page Up gruplar arasında gezer; odak hangi panelde olursa olsun
    for widget in (w.group_view, w.threshold_slider, w.scan_button):
        widget.setFocus()
        w.group_view.setCurrentIndex(w.group_model.index(0))
        QTest.keyClick(widget, Qt.Key.Key_PageDown)
        assert w.current_group is second
        QTest.keyClick(widget, Qt.Key.Key_PageUp)
        assert w.current_group is first

    # ← / → grubun içindeki fotoğraflar arasında gezer, odak çerçevesi kartta
    paths = [m.path for m in first.members]
    w._focus_item(paths[0])
    w.group_view.setFocus()
    QTest.keyClick(w.group_view, Qt.Key.Key_Right)
    assert w.focused_path == paths[1]
    assert w.grid.cards[paths[1]].property("focused") is True
    assert w.grid.cards[paths[0]].property("focused") is False
    QTest.keyClick(w.group_view, Qt.Key.Key_Right)
    QTest.keyClick(w.group_view, Qt.Key.Key_Right)  # sonda durur
    assert w.focused_path == paths[2]
    QTest.keyClick(w.group_view, Qt.Key.Key_Left)
    assert w.focused_path == paths[1]

    # Boşluk odaktaki fotoğrafın işaretini değiştirir
    was = paths[1] in first.marked
    QTest.keyClick(w.group_view, Qt.Key.Key_Space)
    assert (paths[1] in first.marked) is not was
    assert w.grid.cards[paths[1]].mark_box.isChecked() is not was

    # Arama kutusuna yazarken kısayollar çalışmaz
    focused, group = w.focused_path, w.current_group
    w.search_edit.setFocus()
    QTest.keyClick(w.search_edit, Qt.Key.Key_Right)
    QTest.keyClick(w.search_edit, Qt.Key.Key_Space)
    QTest.keyClick(w.search_edit, Qt.Key.Key_PageDown)
    assert w.focused_path == focused == paths[1]
    assert (paths[1] in first.marked) is not was
    assert w.current_group is group
    assert w.search_edit.text() == " "
    w.close()


def test_delete_key_trashes_only_focused_photo(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool, Qt
    from PySide6.QtTest import QTest

    from benzerfoto import actions, recycle

    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    w.show()
    group = w.visible_groups[0]
    paths = [m.path for m in group.members]
    w._focus_item(paths[1])

    sent = []
    monkeypatch.setattr(recycle, "is_trash_supported", lambda p: True)
    monkeypatch.setattr(
        actions, "send_to_trash", lambda db, ps, progress=None: sent.append(list(ps)) or actions.ActionResult(op_id=1, done=list(ps))
    )
    # Önce vazgeç: hiçbir şey gönderilmez
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No))
    w.group_view.setFocus()
    QTest.keyClick(w.group_view, Qt.Key.Key_Delete)
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert sent == []

    # Onaylanınca yalnızca odaktaki dosya gider, odak yanındaki fotoğrafa geçer
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes))
    QTest.keyClick(w.group_view, Qt.Key.Key_Delete)
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert sent == [[paths[1]]]
    assert w.current_group is group
    assert [m.path for m in group.members] == [paths[0], paths[2]]
    assert w.focused_path == paths[2]

    # Korunan fotoğraf gönderilmez
    group.protected.add(paths[2])
    QTest.keyClick(w.group_view, Qt.Key.Key_Delete)
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    assert sent == [[paths[1]]]
    w.close()


def test_reviewed_groups_auto_mark_filter_and_persist(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from benzerfoto.gui.main_window import MainWindow

    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    first, second = w.visible_groups
    assert not first.reviewed and not second.reviewed
    assert w.chip_open.text() == "İncelenmemiş (2)"

    # Sonrakine geçince geçilen grup incelendi olur
    w.group_view.setCurrentIndex(w.group_model.index(0))
    w._step_group(1)
    assert first.reviewed and w.current_group is second and not second.reviewed
    assert w.chip_reviewed.text() == "İncelendi (1)"
    assert not w.reviewed_button.isChecked()

    # Seçim değişince grup incelendi olur; işaretler kaydedilir
    kept = second.members[0].path
    w._keep_only(kept)
    assert second.reviewed and w.reviewed_button.isChecked()

    # Elle kaldırma
    w.reviewed_button.setChecked(False)
    assert not second.reviewed
    assert w.reviewed_groups() == [first]

    # Filtre çipleri
    w.chip_reviewed.setChecked(True)
    assert w.visible_groups == [first]
    w.chip_open.setChecked(True)
    assert w.visible_groups == [second]
    w.chip_all.setChecked(True)

    # İncelenen gruplara uygula: yalnızca incelenen grubun işaretlileri işlenir
    paths, _size, _skipped = w._collect_marked(w.reviewed_groups())
    assert paths and set(paths) <= {m.path for m in first.members}
    first_marks = set(first.marked)
    w.close()

    # Uygulama kapatılıp yeniden açılır, yeniden gruplanır: kararlar geri gelir
    w2 = MainWindow(tmp_path / "db.sqlite", ini_settings(tmp_path))
    w2.features = w.features
    w2._regroup_all()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
    by_first = {g.members[0].path: g for g in w2.groups_by_kind[GroupKind.SCENE]}
    g1, g2 = by_first[first.members[0].path], by_first[second.members[0].path]
    assert g1.reviewed and g1.marked == first_marks
    assert not g2.reviewed  # elle kaldırılmıştı
    assert g2.best_path == kept and kept not in g2.marked  # seçim yine de korunur
    w2.close()


def test_scope_dialog_offers_reviewed_groups(app, tmp_path: Path, monkeypatch):
    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    first = w.visible_groups[0]
    w._mark_reviewed(first)
    seen = {}

    def fake_exec(box):
        seen["buttons"] = [b.text() for b in box.buttons()]
        target = next(b for b in box.buttons() if b.text().startswith("İncelenen gruplara uygula"))
        target.click()
        return 0

    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", fake_exec)
    from benzerfoto.journal import KIND_TRASH

    assert w._ask_scope(KIND_TRASH) == [first]
    assert any(t.startswith("İncelenen gruplara uygula (1 grup") for t in seen["buttons"])
    w.close()


def test_discard_dialog_needs_explicit_confirmation(app):
    from benzerfoto.gui.confirm import DiscardGroupDialog

    dlg = DiscardGroupDialog(3, "2,1 MB")
    assert not dlg.send_button.isEnabled()
    dlg.confirm_box.setChecked(True)
    assert dlg.send_button.isEnabled()
    dlg.confirm_box.setChecked(False)
    assert not dlg.send_button.isEnabled()


def test_discard_whole_group_double_confirmation(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from benzerfoto import actions, recycle
    from benzerfoto.gui import confirm

    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    group = next(g for g in w.visible_groups if len(g.members) == 3)
    w.group_view.setCurrentIndex(w.group_model.index(w.visible_groups.index(group)))
    assert w.current_group is group
    paths = [m.path for m in group.members]
    group.protected.add(paths[0])  # korunan fotoğraf gönderilmez
    group.marked.discard(paths[0])

    sent = []
    monkeypatch.setattr(recycle, "is_trash_supported", lambda p: True)
    monkeypatch.setattr(
        actions, "send_to_trash", lambda db, ps, progress=None: sent.append(list(ps)) or actions.ActionResult(op_id=1, done=list(ps))
    )
    answers = {"first": QtWidgets.QMessageBox.StandardButton.No, "second": 0}
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: answers["first"]))
    monkeypatch.setattr(confirm.DiscardGroupDialog, "exec", lambda self: answers["second"])

    def run():
        w._discard_current_group()
        QThreadPool.globalInstance().waitForDone(10000)
        app.processEvents()

    run()  # ilk soruda vazgeçti
    answers["first"] = QtWidgets.QMessageBox.StandardButton.Yes
    run()  # ikinci pencerede vazgeçti
    assert sent == []

    answers["second"] = confirm.DiscardGroupDialog.DialogCode.Accepted
    run()
    assert sent == [paths[1:]]
    assert all(g is not group for g in w.groups_by_kind[GroupKind.SCENE])  # tek fotoğraf kaldı, grup düştü
    w.close()


def test_f1_opens_shortcut_help_even_from_search_box(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from benzerfoto.gui import shortcuts_help

    opened = []
    monkeypatch.setattr(shortcuts_help.ShortcutsDialog, "exec", lambda self: opened.append(self.label.text()) or 0)
    w = _window_with_group(app, tmp_path, monkeypatch)
    w.show()
    w.search_edit.setFocus()
    QTest.keyClick(w.search_edit, Qt.Key.Key_F1)
    w.help_button.click()
    assert len(opened) == 2
    for key in ("Page Down", "Boşluk", "Delete", "F1"):
        assert key in opened[0]
    w.close()


def test_enter_marks_reviewed_and_moves_on(app, tmp_path: Path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    w = _window_with_two_groups(app, tmp_path, monkeypatch)
    w.show()
    first, second = w.visible_groups
    w.group_view.setCurrentIndex(w.group_model.index(0))
    w.scan_button.setFocus()  # odaktaki düğmeye basılmamalı, kısayol çalışmalı
    QTest.keyClick(w.scan_button, Qt.Key.Key_Return)
    assert first.reviewed and w.current_group is second
    QTest.keyClick(w.group_view, Qt.Key.Key_Enter)  # son grup: incelendi olur, yerinde kalır
    assert second.reviewed and w.current_group is second
    assert w.scan_thread is None

    # Arama kutusunda Enter kısayol değildir
    second.reviewed = False
    w.search_edit.setFocus()
    QTest.keyClick(w.search_edit, Qt.Key.Key_Return)
    assert not second.reviewed
    w.close()


def test_explorer_command_selects_file_with_real_case(tmp_path: Path):
    import os
    import sys

    from benzerfoto.discovery import normalize_path
    from benzerfoto.gui.main_window import explorer_command

    photo = tmp_path / "Tatil Klasörü" / "IMG_0001.JPG"
    photo.parent.mkdir()
    photo.write_bytes(b"x")
    command = explorer_command(normalize_path(str(photo)))  # önbellekteki gibi küçük harf
    if sys.platform != "win32":
        assert command is None
        return
    assert command == ["explorer", "/select,", os.path.realpath(photo)]
    assert command[2].endswith("Tatil Klasörü" + os.sep + "IMG_0001.JPG")  # gerçek yazım
    photo.unlink()  # dosya taşınmışsa klasör açılır
    assert explorer_command(normalize_path(str(photo))) == ["explorer", os.path.realpath(photo.parent)]
