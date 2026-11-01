"""Ayarlar penceresinden değiştirilen kalıcı ayarlar.

QSettings nesnesi dışarıdan verilir: uygulama kendi kayıt defteri anahtarını,
testler geçici bir INI dosyasını kullanır. Eşikler ve zaman penceresi açılış
varsayılanlarıdır; ana penceredeki kaydırıcı yalnızca o oturumu etkiler.
"""

from __future__ import annotations

from dataclasses import dataclass

from benzerfoto.grouping import (
    DEFAULT_SCENE_DISTANCE,
    DEFAULT_SCENE_WINDOW_SECONDS,
    DEFAULT_SIMILAR_DISTANCE,
    distance_to_similarity,
)
from benzerfoto.scanner import default_workers

WINDOW_CHOICES = [10, 30, 60, 120, 300]
THRESHOLD_RANGE = (50, 100)
MAX_WORKERS = 64


@dataclass
class AppSettings:
    similar_threshold: int = round(distance_to_similarity(DEFAULT_SIMILAR_DISTANCE))
    scene_threshold: int = round(distance_to_similarity(DEFAULT_SCENE_DISTANCE))
    scene_window: int = DEFAULT_SCENE_WINDOW_SECONDS
    workers: int = 0  # 0: otomatik

    def effective_workers(self) -> int:
        return self.workers if self.workers > 0 else default_workers()

    @classmethod
    def load(cls, store) -> AppSettings:
        """Kayıtlı değerleri okur; geçersiz ya da eksik olanlar varsayılana döner."""
        d = cls()

        def read_int(key: str, old_key: str | None, fallback: int) -> int:
            # 0.4'te yalnızca son kullanılan değer vardı (old_key); varsa onu devral
            for k in (key, old_key):
                if k and store.contains(k):
                    try:
                        return round(float(store.value(k)))
                    except (TypeError, ValueError):
                        return fallback
            return fallback

        lo, hi = THRESHOLD_RANGE
        similar = read_int("default_threshold_similar", "threshold_similar", d.similar_threshold)
        scene = read_int("default_threshold_scene", "threshold_scene", d.scene_threshold)
        window = read_int("default_window_seconds", "window_seconds", d.scene_window)
        workers = read_int("workers", None, d.workers)
        return cls(
            similar_threshold=similar if lo <= similar <= hi else d.similar_threshold,
            scene_threshold=scene if lo <= scene <= hi else d.scene_threshold,
            scene_window=window if window in WINDOW_CHOICES else d.scene_window,
            workers=workers if 0 <= workers <= MAX_WORKERS else d.workers,
        )

    def save(self, store) -> None:
        store.setValue("default_threshold_similar", self.similar_threshold)
        store.setValue("default_threshold_scene", self.scene_threshold)
        store.setValue("default_window_seconds", self.scene_window)
        store.setValue("workers", self.workers)
