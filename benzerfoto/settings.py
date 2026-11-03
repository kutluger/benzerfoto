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

SETTINGS_VERSION = 3
# 0.4'te yalnızca son kullanılan değer saklanıyordu: yeni anahtar → eski anahtar
_OLD_KEYS = {
    "default_threshold_similar": "threshold_similar",
    "default_threshold_scene": "threshold_scene",
    "default_window_seconds": "window_seconds",
}
WINDOW_CHOICES = [10, 30, 60, 120, 300]


def _read_int(store, key: str, fallback: int) -> int:
    """Elle düzenlenmiş ya da bozuk değerlerde çökmeden varsayılana döner."""
    if not store.contains(key):
        return fallback
    try:
        return round(float(store.value(key)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def migrate_settings(store) -> None:
    """Eski ayar anahtarlarını bir kez yenilerine taşır.

    Yalnızca kullanıcının kaydettiği değerler devralınır; fabrika değerleri yazılmaz,
    böylece ileride değişen bir varsayılan, ayarı hiç değiştirmemiş kullanıcıya da ulaşır.
    """
    version = _read_int(store, "settings_version", 1)
    if version >= SETTINGS_VERSION:
        return
    if version < 2:
        # 2. sürüm: Benzer modunun varsayılanı %80 oldu, eski değer devralınmaz
        store.remove("threshold_similar")
    for new_key, old_key in _OLD_KEYS.items():
        if store.contains(old_key):
            if not store.contains(new_key):
                store.setValue(new_key, store.value(old_key))
            store.remove(old_key)
    store.setValue("settings_version", SETTINGS_VERSION)
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

        lo, hi = THRESHOLD_RANGE
        similar = _read_int(store, "default_threshold_similar", d.similar_threshold)
        scene = _read_int(store, "default_threshold_scene", d.scene_threshold)
        window = _read_int(store, "default_window_seconds", d.scene_window)
        workers = _read_int(store, "workers", d.workers)
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
