"""Fotoğraf özelliklerini saklayan SQLite önbelleği.

Her dosya yolu, boyutu ve değiştirilme zamanı ile birlikte saklanır. Sonraki
taramalarda bu üçü aynıysa dosya yeniden işlenmez.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from dataclasses import astuple, fields
from datetime import datetime
from pathlib import Path

from benzerfoto.discovery import is_under, normalize_path
from benzerfoto.features import ImageFeatures

# Şema değişirse artırılır; eski önbellek silinip yeniden oluşturulur.
SCHEMA_VERSION = 1

_FEATURE_COLUMNS = [f.name for f in fields(ImageFeatures)]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    path         TEXT PRIMARY KEY,
    size         INTEGER NOT NULL,
    mtime_ns     INTEGER NOT NULL,
    content_hash TEXT,
    width        INTEGER,
    height       INTEGER,
    phash        TEXT,
    dhash        TEXT,
    taken_at     TEXT,
    camera       TEXT,
    sharpness    REAL,
    error        TEXT,
    scanned_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_size ON images(size);
CREATE INDEX IF NOT EXISTS idx_images_content_hash ON images(content_hash);
CREATE INDEX IF NOT EXISTS idx_images_taken_at ON images(taken_at);
"""


class FeatureCache:
    """Önbellek veritabanına erişim sınıfı. `with` bloğu ile kullanılabilir."""

    def __init__(self, db_path: str | os.PathLike):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Tarama ayrı bir iş parçacığında çalışır (CLI ve arayüz). Bağlantıyı aynı
        # anda yalnızca bir iş parçacığı kullandığı sürece bu güvenlidir.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # WAL kipi, yazma sırasında okumaya izin verir ve daha hızlıdır
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    # --- yaşam döngüsü ---

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FeatureCache:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is not None and int(row[0]) != SCHEMA_VERSION:
            # Eski sürümün önbelleği: güvenli yol, sıfırdan oluşturmak
            self._conn.executescript("DROP TABLE images;")
            self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

    # --- okuma ---

    def get_index(self) -> dict[str, tuple[int, int]]:
        """Tüm kayıtlar için {yol: (boyut, mtime_ns)} sözlüğü döndürür."""
        return {
            path: (size, mtime_ns)
            for path, size, mtime_ns in self._conn.execute(
                "SELECT path, size, mtime_ns FROM images"
            )
        }

    def get_features(self, paths: Iterable[str] | None = None) -> list[ImageFeatures]:
        """Kayıtları döndürür. `paths` verilirse yalnızca o yollar."""
        cols = ", ".join(_FEATURE_COLUMNS)
        if paths is None:
            rows = self._conn.execute(f"SELECT {cols} FROM images ORDER BY path").fetchall()
        else:
            wanted = list(paths)
            rows = []
            # SQLite parametre sınırına takılmamak için parçalar halinde sorgula
            for i in range(0, len(wanted), 500):
                chunk = wanted[i : i + 500]
                marks = ",".join("?" * len(chunk))
                rows.extend(
                    self._conn.execute(
                        f"SELECT {cols} FROM images WHERE path IN ({marks})", chunk
                    ).fetchall()
                )
            rows.sort(key=lambda r: r[0])
        return [ImageFeatures(*row) for row in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]

    def count_errors(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM images WHERE error IS NOT NULL"
        ).fetchone()[0]

    # --- yazma ---

    def upsert_many(self, items: Iterable[ImageFeatures]) -> None:
        """Kayıtları ekler ya da günceller."""
        now = datetime.now().isoformat(timespec="seconds")
        cols = ", ".join(_FEATURE_COLUMNS + ["scanned_at"])
        marks = ", ".join("?" * (len(_FEATURE_COLUMNS) + 1))
        self._conn.executemany(
            f"INSERT OR REPLACE INTO images({cols}) VALUES({marks})",
            (astuple(item) + (now,) for item in items),
        )
        self._conn.commit()

    def remove_paths(self, paths: Iterable[str]) -> int:
        """Verilen yolların kayıtlarını siler, silinen sayısını döndürür."""
        cur = self._conn.executemany("DELETE FROM images WHERE path = ?", ((p,) for p in paths))
        self._conn.commit()
        return cur.rowcount

    def prune_missing(self, roots: Iterable[str], present: set[str]) -> int:
        """Kök klasörlerin altında olup diskte artık bulunmayan kayıtları siler.

        Taramada bulunmayan ama diskte duran dosyalar (örneğin hariç tutulan bir
        klasördekiler) silinmez; o klasör tekrar dahil edilirse işlem yinelenmez.
        """
        norm_roots = [normalize_path(r) for r in roots]
        stale = [
            path
            for path in self.get_index()
            if path not in present
            and any(is_under(path, r) for r in norm_roots)
            and not os.path.exists(path)
        ]
        return self.remove_paths(stale) if stale else 0
