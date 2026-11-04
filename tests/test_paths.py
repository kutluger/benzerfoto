"""Taşınabilir mod: ayarlar ve önbellek program klasöründe."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from benzerfoto import paths
from benzerfoto.paths import DATA_DIR_ENV, copy_legacy_db, prepare_location, resolve_location


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delattr(sys, "frozen", raising=False)


def fake_exe(monkeypatch, folder: Path) -> None:
    """Paketlenmiş EXE gibi davran: program klasörü `folder` olsun."""
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(folder / "BenzerFoto.exe"))


def make_db(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE t (x INTEGER)")
        con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(rows)])
    con.close()


def test_source_run_uses_local_app_data(tmp_path: Path):
    loc = resolve_location()
    assert not loc.portable
    assert loc.db_path == tmp_path / "LocalAppData" / "BenzerFoto" / "benzerfoto.db"
    assert loc.settings_file is None  # ayarlar kayıt defterinde


def test_exe_is_portable(monkeypatch, tmp_path: Path):
    fake_exe(monkeypatch, tmp_path / "USB" / "BenzerFoto")
    loc = resolve_location()
    assert loc.portable
    assert loc.db_path == tmp_path / "USB" / "BenzerFoto" / "veri" / "benzerfoto.db"
    assert loc.settings_file == tmp_path / "USB" / "BenzerFoto" / "veri" / "ayarlar.ini"


def test_read_only_program_folder_falls_back(monkeypatch, tmp_path: Path):
    fake_exe(monkeypatch, tmp_path / "Program Files" / "BenzerFoto")
    monkeypatch.setattr(paths, "_is_writable", lambda folder: False)
    loc = resolve_location()
    assert not loc.portable
    assert loc.folder == tmp_path / "LocalAppData" / "BenzerFoto"


def test_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / "elle"))
    loc = resolve_location()
    assert loc.portable and loc.folder == tmp_path / "elle"


def test_first_portable_run_copies_old_cache(monkeypatch, tmp_path: Path):
    make_db(tmp_path / "LocalAppData" / "BenzerFoto" / "benzerfoto.db", rows=5)
    fake_exe(monkeypatch, tmp_path / "USB" / "BenzerFoto")
    loc = prepare_location()
    with sqlite3.connect(loc.db_path) as con:
        assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 5
    con.close()


def test_existing_portable_db_is_not_overwritten(tmp_path: Path):
    old, new = tmp_path / "old.db", tmp_path / "veri" / "benzerfoto.db"
    make_db(old, rows=5)
    make_db(new, rows=2)
    assert copy_legacy_db(new, old) is False
    with sqlite3.connect(new) as con:
        assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2
    con.close()


def test_missing_old_cache_is_fine(tmp_path: Path):
    assert copy_legacy_db(tmp_path / "veri" / "benzerfoto.db", tmp_path / "yok.db") is False
    assert not (tmp_path / "veri" / "benzerfoto.db").exists()


def test_settings_copied_from_old_store_once(monkeypatch, tmp_path: Path):
    QtCore = pytest.importorskip("PySide6.QtCore")
    from benzerfoto.gui import app

    old = QtCore.QSettings(str(tmp_path / "eski.ini"), QtCore.QSettings.Format.IniFormat)
    old.setValue("folders_scan", ["D:/Fotoğraflar"])
    old.setValue("default_threshold_similar", 85)
    # Kayıt defteri yerine geçici INI: testler gerçek ayarlara dokunmamalı
    def fake_qsettings(*args):
        return old if not args else QtCore.QSettings(*args)

    fake_qsettings.Format = QtCore.QSettings.Format
    monkeypatch.setattr(app, "QSettings", fake_qsettings)
    fake_exe(monkeypatch, tmp_path / "USB" / "BenzerFoto")

    store = app.open_settings(None)
    assert Path(store.fileName()) == tmp_path / "USB" / "BenzerFoto" / "veri" / "ayarlar.ini"
    assert int(store.value("default_threshold_similar")) == 85

    # İkinci açılışta kopyalama yapılmaz: taşınabilir dosyadaki değer korunur
    store.setValue("default_threshold_similar", 90)
    store.sync()
    old.setValue("default_threshold_similar", 70)
    assert int(app.open_settings(None).value("default_threshold_similar")) == 90

