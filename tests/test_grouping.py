from pathlib import Path

import pytest

from benzerfoto.cache import FeatureCache
from benzerfoto.features import ImageFeatures
from benzerfoto.grouping import (
    GroupKind,
    PhotoGroup,
    build_groups,
    choose_best,
    distance_to_similarity,
    find_exact_duplicates,
    find_scenes,
    find_similar,
    similarity_to_distance,
)
from benzerfoto.scanner import scan
from tests.conftest import make_scene, save_jpeg


def feat(path, size=1000, h="0" * 32, ph="0" * 16, dh="0" * 16, t=None, w=100, hgt=100, sharp=100.0, error=None):
    return ImageFeatures(path, size, 0, h, w, hgt, ph, dh, t, None, sharp, error)


# --- Kopya ---

def test_exact_duplicates_need_same_size_and_hash():
    groups = find_exact_duplicates([
        feat("/a/1.jpg", 1000, "a" * 32),
        feat("/b/1.jpg", 1000, "a" * 32),
        feat("/c/1.jpg", 1000, "b" * 32),  # aynı boyut, farklı içerik
        feat("/d/1.jpg", 2000, "a" * 32),  # imkânsız ama boyut farklı: ayrı tutulur
    ])
    assert len(groups) == 1
    assert [m.path for m in groups[0].members] == ["/a/1.jpg", "/b/1.jpg"]


def test_exact_best_is_shortest_path():
    (g,) = build_groups([feat("/foto/yedek/eski/1.jpg"), feat("/foto/1.jpg")], GroupKind.EXACT)
    assert g.best_path == "/foto/1.jpg"
    assert g.marked == {"/foto/yedek/eski/1.jpg"}


# --- Benzer ---

def test_similar_links_by_both_hashes():
    items = [
        feat("/1.jpg", h="1" * 32, ph="ffffffffffffffff", dh="ffffffffffffffff"),
        feat("/2.jpg", h="2" * 32, ph="fffffffffffffff0", dh="ffffffffffffff00"),  # 4 ve 8 bit
        feat("/3.jpg", h="3" * 32, ph="fffffffffffffff0", dh="0000000000000000"),  # dHash çok farklı
    ]
    (g,) = find_similar(items, max_distance=8)
    assert {m.path for m in g.members} == {"/1.jpg", "/2.jpg"}


def test_similar_skips_groups_of_only_exact_copies():
    items = [feat("/1.jpg", h="a" * 32), feat("/2.jpg", h="a" * 32)]
    assert find_similar(items) == []


def test_similar_prefers_higher_resolution():
    items = [
        feat("/kucuk.jpg", 300, "1" * 32, w=400, hgt=300, sharp=100),
        feat("/buyuk.jpg", 3000, "2" * 32, w=4032, hgt=3024, sharp=100),
    ]
    (g,) = build_groups(items, GroupKind.SIMILAR)
    assert g.best_path == "/buyuk.jpg"


# --- Aynı sahne ---

def test_scene_requires_time_window():
    items = [
        feat("/1.jpg", h="1" * 32, t="2025-08-14T18:42:03"),
        feat("/2.jpg", h="2" * 32, t="2025-08-14T18:42:40"),
        feat("/3.jpg", h="3" * 32, t="2025-08-14T19:30:00"),  # aynı görüntü ama çok sonra
        feat("/4.jpg", h="4" * 32),  # EXIF zamanı yok
    ]
    (g,) = find_scenes(items, window_seconds=60)
    assert [m.path for m in g.members] == ["/1.jpg", "/2.jpg"]


def test_scene_chains_within_window():
    # Her kare bir öncekinden 50 sn sonra: ilk ve son arası 100 sn ama zincir bağlar
    items = [
        feat("/1.jpg", h="1" * 32, t="2025-08-14T18:00:00"),
        feat("/2.jpg", h="2" * 32, t="2025-08-14T18:00:50"),
        feat("/3.jpg", h="3" * 32, t="2025-08-14T18:01:40"),
    ]
    (g,) = find_scenes(items, window_seconds=60)
    assert len(g.members) == 3


def test_scene_best_is_sharpest():
    items = [
        feat("/1.jpg", h="1" * 32, t="2025-08-14T18:00:00", sharp=150),
        feat("/2.jpg", h="2" * 32, t="2025-08-14T18:00:05", sharp=420),
        feat("/3.jpg", h="3" * 32, t="2025-08-14T18:00:09", sharp=300),
    ]
    (g,) = build_groups(items, GroupKind.SCENE)
    assert g.best_path == "/2.jpg"
    assert g.marked == {"/1.jpg", "/3.jpg"}


# --- Koruma kuralları ---

def test_protected_files_are_never_marked(tmp_path: Path):
    keep = str(tmp_path / "Albumler")
    a = feat(str(tmp_path / "Albumler" / "1.jpg"), h="1" * 32, sharp=50)
    b = feat(str(tmp_path / "iPhone" / "1.jpg"), h="2" * 32, sharp=400)
    from benzerfoto.discovery import normalize_path
    a.path, b.path = normalize_path(a.path), normalize_path(b.path)
    g = choose_best(PhotoGroup(GroupKind.SIMILAR, [a, b]), protected_folders=[keep])
    # Korunan dosya daha bulanık olsa da öneri ondan yana, diğeri işaretli
    assert g.best_path == a.path
    assert g.protected == {a.path}
    assert g.marked == {b.path}


def test_unreadable_file_is_not_recommended():
    items = [feat("/bozuk.jpg", h="1" * 32, error="hata", sharp=None), feat("/iyi.jpg", h="2" * 32, sharp=1)]
    g = choose_best(PhotoGroup(GroupKind.SIMILAR, items))
    assert g.best_path == "/iyi.jpg"


def test_similarity_percent_mapping():
    assert similarity_to_distance(100) == 0
    assert similarity_to_distance(50) == 32
    assert similarity_to_distance(10) == 32  # alt sınır
    assert distance_to_similarity(similarity_to_distance(87.5)) == 87.5


# --- Uçtan uca: gerçek dosyalarla ---

def test_end_to_end_modes(tmp_path: Path):
    root = tmp_path / "arsiv"
    # Aynı sahne: 4 kare, kişi kıpırdıyor, birkaç saniye arayla; 2. kare bulanık
    for i, (shift, blur) in enumerate([(0, 0), (8, 2.5), (16, 0), (24, 0)]):
        save_jpeg(make_scene(1, shift=shift, blur=blur), root / "sahne" / f"IMG_{i}.jpg", f"2025:08:14 18:42:{10 + i * 7:02}")
    # Kopya
    original = save_jpeg(make_scene(2), root / "IMG_kopya.jpg", "2025:01:01 10:00:00")
    (root / "yedek").mkdir()
    (root / "yedek" / "IMG_kopya.jpg").write_bytes(original.read_bytes())
    # Benzer: küçültülmüş PNG sürümü
    make_scene(3).resize((400, 300)).save(root / "kucuk.png")
    save_jpeg(make_scene(3), root / "buyuk.jpg")

    with FeatureCache(tmp_path / "db.sqlite") as cache:
        feats = scan([root], cache, workers=1).features

    exact = build_groups(feats, GroupKind.EXACT)
    assert len(exact) == 1 and len(exact[0].members) == 2

    similar = build_groups(feats, GroupKind.SIMILAR)
    sim_names = [{Path(m.path).name for m in g.members} for g in similar]
    assert {"kucuk.png", "buyuk.jpg"} in sim_names
    big = next(g for g in similar if any(m.path.endswith("buyuk.jpg") for m in g.members))
    assert big.best_path.endswith("buyuk.jpg")

    scenes = build_groups(feats, GroupKind.SCENE)
    (scene,) = [g for g in scenes if any("sahne" in m.path for m in g.members)]
    assert len(scene.members) == 4
    assert not scene.best_path.endswith("IMG_1.jpg")  # bulanık kare önerilmez
    assert any(m.path.endswith("IMG_1.jpg") for m in scene.members if m.path in scene.marked)
