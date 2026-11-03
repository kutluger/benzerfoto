from pathlib import Path

import imagehash
import numpy as np
import pytest
from PIL import Image

from benzerfoto.discovery import FileEntry, normalize_path
from benzerfoto.features import HEIF_AVAILABLE, extract_features, laplacian_variance, parse_exif_datetime
from tests.conftest import make_scene, save_jpeg


def _features(path: Path):
    st = path.stat()
    return extract_features(FileEntry(normalize_path(path), st.st_size, st.st_mtime_ns))


def test_basic_features(tmp_path: Path):
    path = save_jpeg(make_scene(1), tmp_path / "a.jpg", "2025:08:14 18:42:03", "iPhone 14 Pro")
    f = _features(path)
    assert f.ok, f.error
    assert (f.width, f.height) == (800, 600)
    assert f.taken_at == "2025-08-14T18:42:03"
    assert f.camera == "iPhone 14 Pro"
    assert len(f.content_hash) == 32
    assert len(f.phash) == 16 and len(f.dhash) == 16
    assert f.sharpness > 0


def test_identical_files_share_content_hash(tmp_path: Path):
    a = save_jpeg(make_scene(1), tmp_path / "a.jpg")
    b = tmp_path / "b.jpg"
    b.write_bytes(a.read_bytes())
    assert _features(a).content_hash == _features(b).content_hash


def test_resized_copy_has_close_phash(tmp_path: Path):
    img = make_scene(1)
    a = save_jpeg(img, tmp_path / "a.jpg")
    b = tmp_path / "b.png"
    img.resize((400, 300)).save(b)
    other = save_jpeg(make_scene(7), tmp_path / "c.jpg")
    fa, fb, fc = _features(a), _features(b), _features(other)
    assert fa.content_hash != fb.content_hash
    dist_same = imagehash.hex_to_hash(fa.phash) - imagehash.hex_to_hash(fb.phash)
    dist_other = imagehash.hex_to_hash(fa.phash) - imagehash.hex_to_hash(fc.phash)
    assert dist_same <= 4 < dist_other


def test_blurred_photo_has_lower_sharpness(tmp_path: Path):
    sharp = _features(save_jpeg(make_scene(1), tmp_path / "net.jpg"))
    blurry = _features(save_jpeg(make_scene(1, blur=3), tmp_path / "bulanik.jpg"))
    assert blurry.sharpness < sharp.sharpness / 2


def test_exif_orientation_swaps_dimensions(tmp_path: Path):
    path = tmp_path / "dik.jpg"
    exif = Image.Exif()
    exif[274] = 6  # 90° saat yönünde döndürülmüş
    make_scene(1).save(path, "JPEG", exif=exif.tobytes())
    f = _features(path)
    assert (f.width, f.height) == (600, 800)


def test_corrupt_file_reports_error(tmp_path: Path):
    path = tmp_path / "bozuk.jpg"
    path.write_bytes(b"bu bir jpeg degil")
    f = _features(path)
    assert not f.ok
    assert f.content_hash is not None  # hash yine de hesaplanır


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif kurulu değil")
def test_heic_is_supported(tmp_path: Path):
    path = tmp_path / "IMG_4821.HEIC"
    make_scene(1).save(path, format="HEIF")
    f = _features(path)
    assert f.ok, f.error
    assert (f.width, f.height) == (800, 600)


def test_parse_exif_datetime():
    assert parse_exif_datetime("2025:08:14 18:42:17") == "2025-08-14T18:42:17"
    assert parse_exif_datetime("2025:08:14 18:42:17\x00") == "2025-08-14T18:42:17"
    assert parse_exif_datetime("0000:00:00 00:00:00") is None
    assert parse_exif_datetime(None) is None


def test_laplacian_flat_image_is_zero():
    assert laplacian_variance(np.full((10, 10), 128, dtype=np.uint8)) == 0.0
