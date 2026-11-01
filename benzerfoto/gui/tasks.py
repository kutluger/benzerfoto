"""Uzun süren işleri arka planda çalıştırma yardımcıları."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal

from benzerfoto.cache import FeatureCache
from benzerfoto.scanner import ScanProgress, scan


class ScanThread(QThread):
    """Taramayı ayrı bir iş parçacığında çalıştırır."""

    progress = Signal(str, int, int)  # aşama, tamamlanan, toplam
    succeeded = Signal(object)  # ScanResult
    failed = Signal(str)

    def __init__(
        self,
        db_path: Path,
        roots: list[str],
        excludes: list[str],
        recursive: bool,
        extensions: Iterable[str],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.db_path = db_path
        self.roots, self.excludes = roots, excludes
        self.recursive = recursive
        self.extensions = list(extensions)
        self.cancel_event = threading.Event()
        self._last_emit = 0.0

    def cancel(self) -> None:
        self.cancel_event.set()

    def _on_progress(self, p: ScanProgress) -> None:
        # Arayüzü boğmamak için en fazla saniyede 10 bildirim gönder
        now = time.monotonic()
        if p.phase == "process" and p.done < p.total and now - self._last_emit < 0.1:
            return
        self._last_emit = now
        self.progress.emit(p.phase, p.done, p.total)

    def run(self) -> None:
        try:
            # SQLite bağlantısı bu iş parçacığında açılır ve kapanır
            with FeatureCache(self.db_path) as cache:
                result = scan(
                    self.roots,
                    cache,
                    excludes=self.excludes,
                    recursive=self.recursive,
                    progress=self._on_progress,
                    cancel_event=self.cancel_event,
                    extensions=self.extensions,
                )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ProgressRelay(QObject):
    """Arka plandaki işin ilerlemesini ana iş parçacığına taşır."""

    changed = Signal(int, int)  # tamamlanan, toplam


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _FunctionTask(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals):
        super().__init__()
        self.fn, self.signals = fn, signals

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn())
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


_alive: set[_Signals] = set()


def run_async(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[str], None] | None = None,
) -> None:
    """`fn`'i arka planda çalıştırır; sonuç ana iş parçacığında `on_done`'a gelir."""
    signals = _Signals()
    _alive.add(signals)  # iş bitene kadar nesne silinmesin

    def finish(result: Any) -> None:
        _alive.discard(signals)
        on_done(result)

    def fail(message: str) -> None:
        _alive.discard(signals)
        if on_error:
            on_error(message)

    signals.finished.connect(finish)
    signals.failed.connect(fail)
    QThreadPool.globalInstance().start(_FunctionTask(fn, signals))
