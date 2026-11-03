import os
import threading
from pathlib import Path

import pytest

from benzerfoto.cache import FeatureCache
from benzerfoto.cli import main
from benzerfoto.scanner import scan
from tests.conftest import make_scene, save_jpeg


@pytest.fixture
def cache(tmp_path: Path):
    with FeatureCache(tmp_path / "onbellek.db") as c:
        yield c


def test_first_scan_processes_everything(photo_dir: Path, cache: FeatureCache):
    r = scan([photo_dir], cache, workers=1)
    assert (r.total_files, r.processed, r.from_cache, r.failed) == (4, 4, 0, 0)
    assert len(r.features) == 4
    assert cache.count() == 4


def test_second_scan_uses_cache(photo_dir: Path, cache: FeatureCache):
    scan([photo_dir], cache, workers=1)
    r = scan([photo_dir], cache, workers=1)
    assert (r.processed, r.from_cache) == (0, 4)
    assert len(r.features) == 4


def test_changed_and_new_files_are_reprocessed(photo_dir: Path, cache: FeatureCache):
    scan([photo_dir], cache, workers=1)
    target = photo_dir / "2025" / "IMG_0001.jpg"
    save_jpeg(make_scene(5), target)  # içerik değişti
    st = target.stat()
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))
    save_jpeg(make_scene(6), photo_dir / "yeni.jpg")

    r = scan([photo_dir], cache, workers=1)
    assert (r.total_files, r.processed, r.from_cache) == (5, 2, 3)


def test_deleted_files_are_removed_from_cache(photo_dir: Path, cache: FeatureCache):
    scan([photo_dir], cache, workers=1)
    (photo_dir / "2025" / "IMG_0003.JPG").unlink()
    r = scan([photo_dir], cache, workers=1)
    assert r.removed == 1
    assert cache.count() == 3


def test_excluded_files_stay_in_cache_but_not_in_result(photo_dir: Path, cache: FeatureCache):
    scan([photo_dir], cache, workers=1)
    r = scan([photo_dir], cache, excludes=[photo_dir / "2025"], workers=1)
    assert len(r.features) == 1
    assert r.removed == 0
    assert cache.count() == 4


def test_parallel_scan_matches_serial(photo_dir: Path, tmp_path: Path):
    with FeatureCache(tmp_path / "seri.db") as c1, FeatureCache(tmp_path / "paralel.db") as c2:
        serial = scan([photo_dir], c1, workers=1).features
        parallel = scan([photo_dir], c2, workers=2).features
    assert serial == parallel


def test_cancel_keeps_partial_progress(photo_dir: Path, cache: FeatureCache):
    for i in range(10):
        save_jpeg(make_scene(20 + i, size=(300, 200)), photo_dir / "seri" / f"IMG_{i:04}.jpg")
    cancel = threading.Event()

    def stop_after_three(p):
        if p.phase == "process" and p.done >= 3:
            cancel.set()

    r = scan([photo_dir], cache, workers=1, progress=stop_after_three, cancel_event=cancel)
    assert r.cancelled
    assert cache.count() == 3

    r2 = scan([photo_dir], cache, workers=1)
    assert not r2.cancelled
    assert (r2.from_cache, r2.processed) == (3, 11)


def test_progress_reports_reach_total(photo_dir: Path, cache: FeatureCache):
    events = []
    scan([photo_dir], cache, workers=1, progress=events.append)
    process = [e for e in events if e.phase == "process"]
    assert process[-1].done == process[-1].total == 4
    assert events[-1].phase == "done"


def test_cache_schema_survives_reopen(photo_dir: Path, tmp_path: Path):
    db = tmp_path / "kalici.db"
    with FeatureCache(db) as c:
        scan([photo_dir], c, workers=1)
    with FeatureCache(db) as c:
        assert c.count() == 4
        assert {f.camera for f in c.get_features()} == {"iPhone 14 Pro", None}


def test_cli_scan_and_info(photo_dir: Path, tmp_path: Path, capsys):
    db = str(tmp_path / "cli.db")
    assert main(["--db", db, "scan", str(photo_dir), "-w", "1"]) == 0
    out = capsys.readouterr().out
    assert "Toplam dosya      : 4" in out
    assert main(["--db", db, "info"]) == 0
    out = capsys.readouterr().out
    assert "Kayıt sayısı : 4" in out
    assert "iPhone 14 Pro 2" in out


def test_cli_rejects_missing_folder(tmp_path: Path):
    assert main(["--db", str(tmp_path / "x.db"), "scan", str(tmp_path / "yok")]) == 2
