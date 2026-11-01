"""Kalıcı ayarlar. Testler gerçek kayıt defterine değil, geçici INI dosyasına yazar."""

from __future__ import annotations

from pathlib import Path

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from benzerfoto.settings import WINDOW_CHOICES, AppSettings  # noqa: E402


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


def test_old_session_values_become_defaults(tmp_path: Path):
    """0.4 sürümünde kaydedilen son eşik/pencere, yeni varsayılan olarak devralınır."""
    store = ini(tmp_path)
    store.setValue("threshold_scene", 75.0)
    store.setValue("window_seconds", 30)
    s = AppSettings.load(store)
    assert s.scene_threshold == 75 and s.scene_window == 30


def test_effective_workers():
    assert AppSettings(workers=2).effective_workers() == 2
    assert AppSettings(workers=0).effective_workers() >= 1
    assert 60 in WINDOW_CHOICES
