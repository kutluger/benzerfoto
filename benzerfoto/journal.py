"""İşlem günlüğü: hangi dosya nereye taşındı ya da kutuya gönderildi.

Önbellekle aynı SQLite dosyasında, ayrı tablolarda tutulur. Her işlem
(taşıma / geri dönüşüm) bir satır, işlemdeki her dosya ayrı bir satırdır.
Geri alma bu kayıtlara göre yapılır.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

KIND_MOVE = "move"
KIND_TRASH = "trash"
KIND_LABELS = {KIND_MOVE: "_benzerler'e taşıma", KIND_TRASH: "Geri Dönüşüm Kutusu"}

# Dosya durumları
DONE, FAILED, RESTORED, RESTORE_FAILED = "done", "failed", "restored", "restore_failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    created_ts  REAL NOT NULL,
    undone_at   TEXT
);
CREATE TABLE IF NOT EXISTS operation_items (
    op_id   INTEGER NOT NULL REFERENCES operations(id),
    src     TEXT NOT NULL,
    dst     TEXT,
    size    INTEGER NOT NULL DEFAULT 0,
    status  TEXT NOT NULL,
    error   TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_op ON operation_items(op_id);
"""


@dataclass
class Operation:
    id: int
    kind: str
    created_at: str
    created_ts: float
    undone_at: str | None
    done_count: int
    done_bytes: int
    failed_count: int

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    @property
    def undoable(self) -> bool:
        return self.undone_at is None and self.done_count > 0


@dataclass
class OperationItem:
    rowid: int
    src: str
    dst: str | None
    size: int
    status: str
    error: str | None


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class Journal:
    """İşlem günlüğüne erişim. `with` bloğu ile kullanılabilir."""

    def __init__(self, db_path: str | os.PathLike):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- yazma ---

    def start(self, kind: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO operations(kind, created_at, created_ts) VALUES(?, ?, ?)",
            (kind, _now(), time.time()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def add_item(self, op_id: int, src: str, dst: str | None, size: int, status: str, error: str | None = None) -> None:
        self._conn.execute(
            "INSERT INTO operation_items(op_id, src, dst, size, status, error) VALUES(?, ?, ?, ?, ?, ?)",
            (op_id, src, dst, size, status, error),
        )

    def set_item_status(self, rowid: int, status: str, error: str | None = None) -> None:
        self._conn.execute("UPDATE operation_items SET status=?, error=? WHERE rowid=?", (status, error, rowid))

    def mark_undone(self, op_id: int) -> None:
        self._conn.execute("UPDATE operations SET undone_at=? WHERE id=?", (_now(), op_id))
        self.commit()

    def commit(self) -> None:
        self._conn.commit()

    # --- okuma ---

    def operations(self, limit: int = 100) -> list[Operation]:
        rows = self._conn.execute(
            f"""
            SELECT o.id, o.kind, o.created_at, o.created_ts, o.undone_at,
                   COALESCE(SUM(i.status IN ('{DONE}', '{RESTORE_FAILED}')), 0),
                   COALESCE(SUM(CASE WHEN i.status IN ('{DONE}', '{RESTORE_FAILED}') THEN i.size END), 0),
                   COALESCE(SUM(i.status = '{FAILED}'), 0)
            FROM operations o LEFT JOIN operation_items i ON i.op_id = o.id
            GROUP BY o.id ORDER BY o.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [Operation(*r) for r in rows]

    def get(self, op_id: int) -> Operation | None:
        return next((o for o in self.operations(10_000) if o.id == op_id), None)

    def last_undoable(self) -> Operation | None:
        return next((o for o in self.operations(1000) if o.undoable), None)

    def items(self, op_id: int) -> list[OperationItem]:
        rows = self._conn.execute(
            "SELECT rowid, src, dst, size, status, error FROM operation_items WHERE op_id=? ORDER BY rowid",
            (op_id,),
        ).fetchall()
        return [OperationItem(*r) for r in rows]
