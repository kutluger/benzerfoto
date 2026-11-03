"""İnceleme durumu: hangi grup incelendi, hangi fotoğraflar işaretli.

Önbellekle aynı SQLite dosyasında, ayrı bir tabloda tutulur. Anahtar grup
değil dosya yoludur (moda göre ayrı): uygulama kapatılıp ertesi gün yeniden
tarama yapılsa, eşik değişse ya da gruba yeni bir fotoğraf katılsa bile
bilinen fotoğrafların kararı geri gelir.

Bir grup, tüm üyelerinin kaydı "incelendi" ise incelenmiş sayılır. Gruba
sonradan yeni bir fotoğraf katıldıysa grup yeniden incelenmemiş görünür ama
eski fotoğrafların işaretleri korunur.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from benzerfoto.grouping import GroupKind, PhotoGroup

_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_state (
    kind        TEXT NOT NULL,
    path        TEXT NOT NULL,
    reviewed    INTEGER NOT NULL,
    marked      INTEGER NOT NULL,
    best        INTEGER NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (kind, path)
);
"""


@dataclass(frozen=True)
class FileDecision:
    reviewed: bool
    marked: bool
    best: bool


class ReviewStore:
    """İnceleme kayıtlarına erişim. `with` bloğu ile kullanılabilir."""

    def __init__(self, db_path: str | os.PathLike):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ReviewStore:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def save_group(self, group: PhotoGroup) -> None:
        """Grubun inceleme durumunu ve her üyenin işaretini yazar."""
        now = datetime.now().isoformat(timespec="seconds")
        self._conn.executemany(
            "INSERT OR REPLACE INTO review_state(kind, path, reviewed, marked, best, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
            (
                (
                    group.kind.value,
                    m.path,
                    int(group.reviewed),
                    int(m.path in group.marked),
                    int(m.path == group.best_path),
                    now,
                )
                for m in group.members
            ),
        )
        self._conn.commit()

    def load(self, kind: GroupKind) -> dict[str, FileDecision]:
        rows = self._conn.execute(
            "SELECT path, reviewed, marked, best FROM review_state WHERE kind = ?", (kind.value,)
        )
        return {path: FileDecision(bool(r), bool(m), bool(b)) for path, r, m, b in rows}

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM review_state").fetchone()[0]


def apply_decisions(groups: Iterable[PhotoGroup], decisions: dict[str, FileDecision]) -> None:
    """Kayıtlı kararları yeni hesaplanan gruplara uygular.

    Korunan dosyalar kayıtta işaretli görünse bile işaretlenmez.
    """
    if not decisions:
        return
    for group in groups:
        known = [decisions.get(m.path) for m in group.members]
        if not any(known):
            continue
        for member, decision in zip(group.members, known):
            if decision is None:
                continue
            if decision.best:
                group.best_path = member.path
            if decision.marked and member.path not in group.protected:
                group.marked.add(member.path)
            else:
                group.marked.discard(member.path)
        group.reviewed = all(d is not None and d.reviewed for d in known)


def load_and_apply(db_path: str | os.PathLike, groups_by_kind: dict[GroupKind, list[PhotoGroup]]) -> None:
    """Her moddaki gruplara kayıtlı kararları uygular (arka plan iş parçacığında da çalışır)."""
    with ReviewStore(db_path) as store:
        for kind, groups in groups_by_kind.items():
            apply_decisions(groups, store.load(kind))
