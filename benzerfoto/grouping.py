"""Gruplama: birebir kopya, benzer görüntü ve aynı sahne grupları.

Her mod, tarama sonucundaki `ImageFeatures` listesini alır ve `PhotoGroup`
listesi döndürür. Gruplarda en iyi fotoğraf önerilir (★) ve geri kalanlar
varsayılan olarak "ayrılacak" diye işaretlenir. Koruma kuralına giren
dosyalar hiçbir zaman işaretlenmez.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np

from benzerfoto.discovery import is_under, normalize_path
from benzerfoto.features import ImageFeatures

# Varsayılan eşikler (64 bitlik hash'lerde farklı bit sayısı)
# Benzer: 13 bit ≈ %80. Denemelerde en kararlı sonuç: %60'ta alakasız
# fotoğraflar eşleşiyor, %80'in üstünde çok benzeyenler kaçıyor.
DEFAULT_SIMILAR_DISTANCE = 13  # farklı boyut/format, hafif düzenleme
DEFAULT_SCENE_DISTANCE = 18  # elle tekrar çekim: kıpırdanma ve küçük kadraj farkları
DEFAULT_SCENE_WINDOW_SECONDS = 60
HASH_BITS = 64


class GroupKind(str, Enum):
    EXACT = "exact"
    SIMILAR = "similar"
    SCENE = "scene"

    @property
    def label(self) -> str:
        """Arayüzde gösterilecek Türkçe ad."""
        return {"exact": "Kopya", "similar": "Benzer", "scene": "Aynı sahne"}[self.value]


@dataclass
class PhotoGroup:
    """Bir arada gösterilecek fotoğraf grubu."""

    kind: GroupKind
    members: list[ImageFeatures]
    best_path: str | None = None
    marked: set[str] = field(default_factory=set)  # ayrılmak üzere işaretli yollar
    protected: set[str] = field(default_factory=set)  # koruma kuralına giren yollar

    @property
    def total_size(self) -> int:
        return sum(m.size for m in self.members)

    @property
    def marked_size(self) -> int:
        return sum(m.size for m in self.members if m.path in self.marked)

    @property
    def best(self) -> ImageFeatures | None:
        return next((m for m in self.members if m.path == self.best_path), None)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


class _UnionFind:
    """Birbirine bağlanan öğeleri gruplara toplar (bağlı bileşenler)."""

    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def components(self) -> list[list[int]]:
        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self.parent)):
            groups[self.find(i)].append(i)
        return [g for g in groups.values() if len(g) > 1]


def _hash_array(hex_hashes: Sequence[str]) -> np.ndarray:
    """16 haneli onaltılık hash metinlerini uint64 dizisine çevirir."""
    return np.array([int(h, 16) for h in hex_hashes], dtype=np.uint64)


def hamming(a: str, b: str) -> int:
    """İki onaltılık hash arasındaki farklı bit sayısı."""
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _parse_time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# En iyiyi önerme
# ---------------------------------------------------------------------------


def quality_score(item: ImageFeatures, group: Sequence[ImageFeatures], kind: GroupKind) -> float:
    """Grup içindeki göreli kalite puanı (0-1 arası).

    Netlik, çözünürlük ve dosya boyutu grubun en yükseğine oranlanır.
    Aynı sahne modunda netlik daha ağırdır: o anı en iyi anlatan genellikle
    titremesiz, en net karedir.
    """

    def ratio(value: float | None, best: float) -> float:
        return (value or 0) / best if best > 0 else 0.0

    max_sharp = max((m.sharpness or 0) for m in group)
    max_pixels = max((m.width or 0) * (m.height or 0) for m in group)
    max_size = max(m.size for m in group)

    w_sharp, w_pixels, w_size = (0.6, 0.3, 0.1) if kind == GroupKind.SCENE else (0.4, 0.45, 0.15)
    return (
        w_sharp * ratio(item.sharpness, max_sharp)
        + w_pixels * ratio((item.width or 0) * (item.height or 0), max_pixels)
        + w_size * ratio(item.size, max_size)
    )


def choose_best(
    group: PhotoGroup, protected_folders: Iterable[str] = ()
) -> PhotoGroup:
    """Grubun en iyisini seçer ve işaretlemeleri ayarlar.

    - Koruma kuralına giren dosyalar asla işaretlenmez.
    - Grupta korunan dosya varsa öneri onların arasından yapılır.
    - Birebir kopyalarda içerik aynı olduğundan önce korunan, sonra en kısa
      yoldaki (genellikle "asıl" klasördeki) dosya önerilir.
    """
    folders = [normalize_path(f) for f in protected_folders]
    group.protected = {
        m.path for m in group.members if any(is_under(m.path, f) for f in folders)
    }
    candidates = [m for m in group.members if m.path in group.protected] or group.members
    # Okunamayan dosyalar yalnızca başka seçenek yoksa önerilir
    candidates = [m for m in candidates if m.ok] or candidates

    if group.kind == GroupKind.EXACT:
        best = min(candidates, key=lambda m: (len(m.path), m.path))
    else:
        best = max(
            candidates,
            key=lambda m: (quality_score(m, group.members, group.kind), -len(m.path)),
        )
    group.best_path = best.path
    group.marked = {
        m.path for m in group.members if m.path != best.path and m.path not in group.protected
    }
    return group


# ---------------------------------------------------------------------------
# Modlar
# ---------------------------------------------------------------------------


def find_exact_duplicates(features: Iterable[ImageFeatures]) -> list[PhotoGroup]:
    """Birebir aynı dosyalar: önce boyut, sonra içerik hash'i aynı olanlar."""
    by_size: dict[int, list[ImageFeatures]] = defaultdict(list)
    for f in features:
        if f.content_hash:
            by_size[f.size].append(f)

    groups = []
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        by_hash: dict[str, list[ImageFeatures]] = defaultdict(list)
        for f in same_size:
            by_hash[f.content_hash].append(f)
        groups.extend(
            PhotoGroup(GroupKind.EXACT, sorted(m, key=lambda x: x.path))
            for m in by_hash.values()
            if len(m) > 1
        )
    return groups


def _is_only_exact_copies(members: Sequence[ImageFeatures]) -> bool:
    return len({m.content_hash for m in members}) == 1


def find_similar(
    features: Iterable[ImageFeatures], max_distance: int = DEFAULT_SIMILAR_DISTANCE
) -> list[PhotoGroup]:
    """Görsel olarak çok benzeyen fotoğraflar (farklı boyut/format, hafif düzenleme).

    pHash ve dHash'in ikisi de eşiğin altındaysa iki fotoğraf benzer sayılır.
    İki hash birlikte kullanılınca yanlış eşleşme belirgin şekilde azalır.
    Karşılaştırma numpy ile toplu yapılır; 50 bin fotoğrafta birkaç saniye sürer.
    Yalnızca birebir kopyalardan oluşan gruplar "Kopya" modunda gösterildiği
    için burada atlanır.
    """
    items = [f for f in features if f.ok and f.phash and f.dhash]
    n = len(items)
    if n < 2:
        return []
    ph = _hash_array([f.phash for f in items])
    dh = _hash_array([f.dhash for f in items])
    uf = _UnionFind(n)
    for i in range(n - 1):
        dp = np.bitwise_count(ph[i + 1 :] ^ ph[i])
        dd = np.bitwise_count(dh[i + 1 :] ^ dh[i])
        for j in np.nonzero((dp <= max_distance) & (dd <= max_distance))[0]:
            uf.union(i, i + 1 + int(j))

    groups = []
    for comp in uf.components():
        members = sorted((items[i] for i in comp), key=lambda x: x.path)
        if not _is_only_exact_copies(members):
            groups.append(PhotoGroup(GroupKind.SIMILAR, members))
    return groups


def find_scenes(
    features: Iterable[ImageFeatures],
    max_distance: int = DEFAULT_SCENE_DISTANCE,
    window_seconds: float = DEFAULT_SCENE_WINDOW_SECONDS,
) -> list[PhotoGroup]:
    """Aynı sahnenin elle tekrar tekrar çekilmiş kareleri.

    Kişilerin kıpırdaması ve küçük kadraj farkları nedeniyle eşik "Benzer"
    modundan daha toleranslıdır. Yanlış eşleşmeyi önlemek için iki karenin
    EXIF çekim zamanları arasında en fazla `window_seconds` saniye olmalı ve
    pHash ile dHash birlikte eşiğin altında kalmalıdır.
    Zincirleme bağlanır: 1-2 ve 2-3 benzerse üçü aynı gruba girer, bu sayede
    sahne yavaşça değişse bile grup bölünmez. EXIF zamanı olmayanlar atlanır.
    """
    timed = [
        (t, f)
        for f in features
        if f.ok and f.phash and f.dhash and (t := _parse_time(f.taken_at)) is not None
    ]
    timed.sort(key=lambda x: (x[0], x[1].path))
    n = len(timed)
    if n < 2:
        return []
    times = np.array([t for t, _ in timed])
    ph = _hash_array([f.phash for _, f in timed])
    dh = _hash_array([f.dhash for _, f in timed])
    uf = _UnionFind(n)
    for i in range(n - 1):
        # Zaman sıralı olduğu için yalnızca pencere içindeki sonraki kareler
        end = int(np.searchsorted(times, times[i] + window_seconds, side="right"))
        if end <= i + 1:
            continue
        dp = np.bitwise_count(ph[i + 1 : end] ^ ph[i])
        dd = np.bitwise_count(dh[i + 1 : end] ^ dh[i])
        # dHash için biraz daha pay bırakılır; ikisinin birlikte tutması
        # rastgele eşleşmeleri neredeyse sıfıra indirir
        for j in np.nonzero((dp <= max_distance) & (dd <= max_distance + 4))[0]:
            uf.union(i, i + 1 + int(j))

    groups = []
    for comp in uf.components():
        members = [timed[i][1] for i in sorted(comp)]  # çekim sırasına göre
        if not _is_only_exact_copies(members):
            groups.append(PhotoGroup(GroupKind.SCENE, members))
    return groups


def build_groups(
    features: Sequence[ImageFeatures],
    kind: GroupKind,
    max_distance: int | None = None,
    window_seconds: float = DEFAULT_SCENE_WINDOW_SECONDS,
    protected_folders: Iterable[str] = (),
) -> list[PhotoGroup]:
    """Seçilen moda göre grupları bulur, en iyiyi önerir ve büyükten küçüğe sıralar."""
    if kind == GroupKind.EXACT:
        groups = find_exact_duplicates(features)
    elif kind == GroupKind.SIMILAR:
        groups = find_similar(features, max_distance if max_distance is not None else DEFAULT_SIMILAR_DISTANCE)
    else:
        groups = find_scenes(
            features,
            max_distance if max_distance is not None else DEFAULT_SCENE_DISTANCE,
            window_seconds,
        )
    protected = list(protected_folders)
    for g in groups:
        choose_best(g, protected)
    groups.sort(key=lambda g: (-g.marked_size, g.members[0].path))
    return groups


def similarity_to_distance(percent: float) -> int:
    """Arayüzdeki benzerlik yüzdesini (50-100) hash bit farkına çevirir.

    %100 → 0 bit (yalnızca aynısı), %50 → 32 bit (çok esnek).
    """
    percent = min(100.0, max(50.0, percent))
    return round((100.0 - percent) / 100.0 * HASH_BITS)


def distance_to_similarity(distance: int) -> float:
    return 100.0 - distance / HASH_BITS * 100.0


__all__ = [
    "GroupKind",
    "PhotoGroup",
    "build_groups",
    "choose_best",
    "find_exact_duplicates",
    "find_scenes",
    "find_similar",
    "hamming",
    "quality_score",
    "similarity_to_distance",
    "distance_to_similarity",
]
