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


@pytest.fixture(scope="module")
def app():
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.setOrganizationName("BenzerFotoTest")
    QCoreApplication.setApplicationName("BenzerFotoTest")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_window_shows_groups(app, tmp_path: Path):
    from PySide6.QtCore import QSettings, QThreadPool

    from benzerfoto.gui.main_window import FOLDER_PROTECT, MainWindow

    QSettings().clear()  # test kuruluşunun ayarları; uygulamanınkine dokunulmaz
    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8, blur=2 if i == 1 else 0), root / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    with FeatureCache(tmp_path / "db.sqlite") as cache:
        features = scan([root], cache, workers=1).features

    w = MainWindow(tmp_path / "db.sqlite")
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
    from PySide6.QtCore import QSettings, QThreadPool

    from benzerfoto import actions
    from benzerfoto.cache import FeatureCache as Cache
    from benzerfoto.gui.main_window import FOLDER_SCAN, MainWindow
    from benzerfoto.journal import KIND_MOVE

    # Bilgi pencereleri testi bekletmesin
    for name in ("information", "warning"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: None))

    QSettings().clear()
    root = tmp_path / "arsiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8, blur=2 if i == 1 else 0), root / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    db = tmp_path / "db.sqlite"
    with Cache(db) as cache:
        features = scan([root], cache, workers=1).features

    w = MainWindow(db)
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
