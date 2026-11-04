"""Ayarların ve önbellek veritabanının nerede tutulacağına karar verir.

Taşınabilir mod: paketlenmiş EXE, verilerini kendi klasöründeki `veri` alt
klasörüne yazar (ayarlar.ini + benzerfoto.db). Böylece USB bellekteki klasör
her bilgisayarda aynı ayarlarla ve aynı önbellekle çalışır. Klasör yazılamıyorsa
(ör. Program Files) eski konuma, %LOCALAPPDATA%\\BenzerFoto'ya dönülür.

Python ile kaynaktan çalıştırınca (baslat.bat) davranış değişmez: veritabanı
%LOCALAPPDATA%'da, ayarlar kayıt defterindedir.

BENZERFOTO_DATA_DIR ortam değişkeni verilirse her durumda o klasör taşınabilir
klasör gibi kullanılır (testler ve elle deneme için).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

DATA_DIR_ENV = "BENZERFOTO_DATA_DIR"
PORTABLE_FOLDER_NAME = "veri"
DB_FILE_NAME = "benzerfoto.db"
SETTINGS_FILE_NAME = "ayarlar.ini"


@dataclass(frozen=True)
class DataLocation:
    folder: Path
    portable: bool  # True: ayarlar INI dosyasında, False: kayıt defterinde

    @property
    def db_path(self) -> Path:
        return self.folder / DB_FILE_NAME

    @property
    def settings_file(self) -> Path | None:
        return self.folder / SETTINGS_FILE_NAME if self.portable else None


def legacy_data_dir() -> Path:
    """Taşınabilir mod öncesindeki (ve kaynaktan çalışırken kullanılan) konum."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    return Path(local_app_data) / "BenzerFoto" if local_app_data else Path.home() / ".benzerfoto"


def program_dir() -> Path | None:
    """Paketlenmiş EXE'nin bulunduğu klasör; kaynaktan çalışırken None."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def _is_writable(folder: Path) -> bool:
    """Klasörü oluşturup içine deneme dosyası yazabiliyor muyuz?"""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".yazma-denemesi"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_location() -> DataLocation:
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return DataLocation(Path(override), portable=True)
    exe_dir = program_dir()
    if exe_dir is not None:
        folder = exe_dir / PORTABLE_FOLDER_NAME
        if _is_writable(folder):
            return DataLocation(folder, portable=True)
    return DataLocation(legacy_data_dir(), portable=False)


def copy_legacy_db(target: Path, source: Path | None = None) -> bool:
    """Taşınabilir klasörde henüz veritabanı yoksa eski önbelleği bir kez kopyalar.

    Böylece ilk açılışta tarama sonuçları, inceleme kararları ve geri alma günlüğü
    kaybolmaz. SQLite yedekleme işlevi kullanılır: WAL dosyasındaki son yazmalar da
    kopyaya dahil olur. Kopyalanamazsa boş veritabanıyla devam edilir.
    """
    source = source or legacy_data_dir() / DB_FILE_NAME
    if target.exists() or not source.is_file() or source.resolve() == target.resolve():
        return False
    tmp = target.with_name(target.name + ".kopyalaniyor")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.unlink(missing_ok=True)
        src = sqlite3.connect(source)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        tmp.replace(target)
        return True
    except (OSError, sqlite3.Error):
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def prepare_location() -> DataLocation:
    """Konumu belirler; EXE taşınabilir moda ilk kez geçiyorsa eski önbelleği kopyalar."""
    location = resolve_location()
    if location.portable and program_dir() is not None:
        copy_legacy_db(location.db_path)
    return location
