from pathlib import Path

from benzerfoto.discovery import is_under, iter_image_files, normalize_path
from tests.conftest import make_scene, save_jpeg


def _names(entries):
    return sorted(Path(e.path).name.lower() for e in entries)


def test_finds_supported_images_recursively(photo_dir: Path):
    found = list(iter_image_files([photo_dir]))
    assert _names(found) == ["ekran.png", "img_0001.jpg", "img_0002.jpg", "img_0003.jpg"]
    assert all(e.size > 0 and e.mtime_ns > 0 for e in found)


def test_non_recursive(photo_dir: Path):
    save_jpeg(make_scene(9), photo_dir / "kok.jpg")
    assert _names(iter_image_files([photo_dir], recursive=False)) == ["kok.jpg"]


def test_excluded_folder_is_skipped(photo_dir: Path):
    found = list(iter_image_files([photo_dir], excludes=[photo_dir / "2025"]))
    assert _names(found) == ["ekran.png"]


def test_duplicates_folder_is_always_skipped(photo_dir: Path):
    save_jpeg(make_scene(1), photo_dir / "_benzerler" / "2025" / "IMG_0001.jpg")
    assert "_benzerler" not in "".join(e.path for e in iter_image_files([photo_dir]))


def test_overlapping_roots_do_not_duplicate(photo_dir: Path):
    found = list(iter_image_files([photo_dir, photo_dir / "2025"]))
    assert len(found) == 4


def test_is_under():
    base = normalize_path("/a/foto")
    assert is_under(normalize_path("/a/foto/x.jpg"), base)
    assert is_under(base, base)
    assert not is_under(normalize_path("/a/fotograflar/x.jpg"), base)
