"""Kalıcı ayarlar. Testler gerçek kayıt defterine değil, geçici INI dosyasına yazar."""

from __future__ import annotations

from pathlib import Path

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from benzerfoto.settings import WINDOW_CHOICES, AppSettings, migrate_settings  # noqa: E402


def ini(tmp_path: Path):
    return QtCore.QSettings(str(tmp_path / "ayarlar.ini"), QtCore.QSettings.Format.IniFormat)


def test_defaults_when_empty(tmp_path: Path):
    s = AppSettings.load(ini(tmp_path))
    assert s == AppSettings()
    assert s.similar_threshold == 80 and s.scene_window == 60 and s.workers == 0


def test_round_trip(tmp_path: Path):
    store = ini(tmp_path)
    AppSettings(similar_threshold=85, scene_threshold=70, scene_window=120, workers=3).save(store)
    store.sync()
    again = AppSettings.load(ini(tmp_path))
    assert again == AppSettings(similar_threshold=85, scene_threshold=70, scene_window=120, workers=3)


def test_invalid_values_fall_back(tmp_path: Path):
    store = ini(tmp_path)
    store.setValue("default_threshold_similar", 7)  # aralık dışı
    store.setValue("default_window_seconds", 45)  # seçeneklerde yok
    store.setValue("workers", -2)
    s = AppSettings.load(store)
    assert s.similar_threshold == AppSettings().similar_threshold
    assert s.scene_window == 60 and s.workers == 0


def _old_store(tmp_path: Path, version: int | None):
    store = ini(tmp_path)
    if version is not None:
        store.setValue("settings_version", version)
    store.setValue("threshold_similar", 60.0)
    store.setValue("threshold_scene", 75.0)
    store.setValue("window_seconds", 30)
    return store


def test_migration_from_version_1(tmp_path: Path):
    """0.3 ve öncesi: Benzer eşiği devralınmaz (varsayılan %80 oldu), diğerleri devralınır."""
    store = _old_store(tmp_path, None)
    migrate_settings(store)
    s = AppSettings.load(store)
    assert s.similar_threshold == AppSettings().similar_threshold
    assert s.scene_threshold == 75 and s.scene_window == 30
    assert not any(store.contains(k) for k in ("threshold_similar", "threshold_scene", "window_seconds"))
    assert int(store.value("settings_version")) == 3
    assert not store.contains("default_threshold_similar")  # fabrika değeri yazılmaz
    migrate_settings(store)  # ikinci kez çalışınca bir şey değişmez
    assert AppSettings.load(store) == s


def test_migration_from_version_2(tmp_path: Path):
    store = _old_store(tmp_path, 2)
    migrate_settings(store)
    s = AppSettings.load(store)
    assert (s.similar_threshold, s.scene_threshold, s.scene_window) == (60, 75, 30)
    assert int(store.value("settings_version")) == 3


def test_migration_skipped_when_current(tmp_path: Path):
    store = _old_store(tmp_path, 3)
    migrate_settings(store)
    assert store.contains("threshold_similar")  # 3. sürümde dokunulmaz
    assert AppSettings.load(store) == AppSettings()


def test_fresh_install_writes_nothing_but_version(tmp_path: Path):
    store = ini(tmp_path)
    migrate_settings(store)
    assert store.allKeys() == ["settings_version"]


def test_garbage_values_do_not_crash(tmp_path: Path):
    store = ini(tmp_path)
    store.setValue("default_threshold_scene", "inf")
    store.setValue("workers", "abc")
    assert AppSettings.load(store) == AppSettings()


def test_effective_workers():
    assert AppSettings(workers=2).effective_workers() == 2
    assert AppSettings(workers=0).effective_workers() >= 1
    assert 60 in WINDOW_CHOICES
