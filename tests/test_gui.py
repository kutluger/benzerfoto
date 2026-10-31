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

    QSettings("BenzerFoto", "BenzerFoto").clear()
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
