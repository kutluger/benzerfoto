"""Tarama motoru: dosyaları bulur, önbelleği kontrol eder, yeni ve değişen
dosyaları çok çekirdekli olarak işler.

Arayüz (3. aşama) bu modülü ayrı bir iş parçacığında çağıracak; ilerleme
`progress` geri çağırma fonksiyonuyla bildirilir, iptal için `cancel_event`
kullanılır.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass, field

from benzerfoto.cache import FeatureCache
from benzerfoto.config import DB_BATCH_SIZE
from benzerfoto.discovery import FileEntry, iter_image_files
from benzerfoto.features import ImageFeatures, extract_features


@dataclass
class ScanProgress:
    """İlerleme bildirimi.

    phase: "discover" (dosyalar aranıyor), "process" (dosyalar işleniyor) ya da "done"
    """

    phase: str
    done: int = 0
    total: int = 0
    current_path: str | None = None


@dataclass
class ScanResult:
    """Taramanın özeti ve taranan kapsamdaki tüm dosyaların özellikleri."""

    total_files: int = 0
    total_bytes: int = 0
    from_cache: int = 0
    processed: int = 0
    failed: int = 0
    removed: int = 0
    elapsed: float = 0.0
    cancelled: bool = False
    features: list[ImageFeatures] = field(default_factory=list)


ProgressCallback = Callable[[ScanProgress], None]


def _ignore_sigint() -> None:
    """Alt süreçler Ctrl+C'yi yok sayar; iptali ana süreç `cancel_event` ile yönetir."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def default_workers() -> int:
    """İşlemci çekirdek sayısının bir eksiği (arayüz akıcı kalsın diye), en az 1."""
    return max(1, (os.cpu_count() or 2) - 1)


def scan(
    roots: Iterable[str | os.PathLike],
    cache: FeatureCache,
    excludes: Iterable[str | os.PathLike] = (),
    recursive: bool = True,
    workers: int | None = None,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    """Klasörleri tarar ve sonucu döndürür.

    İptal edilirse o ana kadar işlenen dosyalar önbelleğe yazılmış olur; bir
    sonraki tarama kaldığı yerden devam eder.
    """
    started = time.perf_counter()
    roots = [os.fspath(r) for r in roots]
    excludes = [os.fspath(e) for e in excludes]
    cancel_event = cancel_event or threading.Event()
    notify = progress or (lambda _p: None)
    result = ScanResult()

    # 1) Dosyaları bul
    entries: list[FileEntry] = []
    for entry in iter_image_files(roots, excludes, recursive):
        entries.append(entry)
        if len(entries) % 500 == 0:
            notify(ScanProgress("discover", done=len(entries), current_path=entry.path))
        if cancel_event.is_set():
            result.cancelled = True
            result.elapsed = time.perf_counter() - started
            return result
    result.total_files = len(entries)
    result.total_bytes = sum(e.size for e in entries)

    # 2) Önbellekle karşılaştır: yol, boyut ve değiştirilme zamanı aynıysa atla
    index = cache.get_index()
    pending = [e for e in entries if index.get(e.path) != (e.size, e.mtime_ns)]
    result.from_cache = len(entries) - len(pending)
    result.removed = cache.prune_missing(roots, {e.path for e in entries})

    # 3) Yeni ve değişen dosyaları işle
    total = len(pending)
    notify(ScanProgress("process", done=0, total=total))
    worker_count = workers if workers is not None else default_workers()
    if worker_count <= 1:
        _process_serial(pending, cache, result, notify, cancel_event)
    else:
        _process_parallel(pending, cache, result, notify, cancel_event, worker_count)

    # 4) Sonuç: taranan kapsamdaki tüm dosyaların güncel kaydı
    result.features = cache.get_features(e.path for e in entries)
    result.elapsed = time.perf_counter() - started
    notify(ScanProgress("done", done=result.processed, total=total))
    return result


def _record(batch: list[ImageFeatures], item: ImageFeatures, result: ScanResult) -> None:
    batch.append(item)
    result.processed += 1
    if not item.ok:
        result.failed += 1


def _process_serial(
    pending: list[FileEntry],
    cache: FeatureCache,
    result: ScanResult,
    notify: ProgressCallback,
    cancel_event: threading.Event,
) -> None:
    """Tek çekirdekte işler (hata ayıklama ve testler için)."""
    batch: list[ImageFeatures] = []
    for entry in pending:
        if cancel_event.is_set():
            result.cancelled = True
            break
        _record(batch, extract_features(entry), result)
        if len(batch) >= DB_BATCH_SIZE:
            cache.upsert_many(batch)
            batch.clear()
        notify(ScanProgress("process", result.processed, len(pending), entry.path))
    if batch:
        cache.upsert_many(batch)


def _process_parallel(
    pending: list[FileEntry],
    cache: FeatureCache,
    result: ScanResult,
    notify: ProgressCallback,
    cancel_event: threading.Event,
    worker_count: int,
) -> None:
    """Birden fazla süreçte işler.

    Bellek ve iptal tepkisi için aynı anda en fazla `worker_count * 4` iş
    kuyrukta bekletilir; hepsi tek seferde gönderilmez.
    """
    batch: list[ImageFeatures] = []
    queue_limit = worker_count * 4
    next_index = 0
    running: set[Future[ImageFeatures]] = set()

    # Windows'ta zaten "spawn" kullanılır; her sistemde aynı davranması için açıkça seçilir
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=worker_count, mp_context=context, initializer=_ignore_sigint
    ) as pool:
        while next_index < len(pending) or running:
            # Kuyruğu doldur
            while not cancel_event.is_set() and next_index < len(pending) and len(running) < queue_limit:
                running.add(pool.submit(extract_features, pending[next_index]))
                next_index += 1

            if cancel_event.is_set():
                result.cancelled = True
                for fut in running:
                    fut.cancel()
                # Zaten çalışmakta olanların bitmesini bekle ve sonuçlarını kaydet
                done, _ = wait(running)
                for fut in done:
                    if not fut.cancelled():
                        _record(batch, fut.result(), result)
                running.clear()
                break

            # İptali hızlı fark etmek için kısa zaman aşımıyla bekle
            done, running = wait(running, timeout=0.2, return_when=FIRST_COMPLETED)
            for fut in done:
                item = fut.result()
                _record(batch, item, result)
                notify(ScanProgress("process", result.processed, len(pending), item.path))
            if len(batch) >= DB_BATCH_SIZE:
                cache.upsert_many(batch)
                batch.clear()

    if batch:
        cache.upsert_many(batch)
