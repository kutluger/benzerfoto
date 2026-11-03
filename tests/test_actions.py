"""Taşıma, geri dönüşüm, işlem günlüğü ve geri alma testleri."""

import os
import sys
from pathlib import Path

import pytest

from benzerfoto import actions, recycle
from benzerfoto.discovery import normalize_path
from benzerfoto.journal import DONE, FAILED, KIND_MOVE, KIND_TRASH, RESTORE_FAILED, RESTORED, Journal


def write(path: Path, data: bytes = b"veri") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_target_keeps_subfolders_and_case(tmp_path: Path):
    root = tmp_path / "Foto"
    f = write(root / "2020" / "Yaz" / "IMG_0001.JPG")
    # Önbellekteki gibi normalize edilmiş (Windows'ta küçük harf) yol verilir
    target = actions.duplicates_target(normalize_path(f), [str(root)])
    expected = os.path.realpath(root) + os.sep + os.path.join("_benzerler", "2020", "Yaz", "IMG_0001.JPG")
    assert target == expected


def test_target_uses_deepest_root(tmp_path: Path):
    outer, inner = tmp_path / "a", tmp_path / "a" / "b"
    f = write(inner / "x.jpg")
    target = actions.duplicates_target(str(f), [str(outer), str(inner)])
    assert Path(target).parent == Path(os.path.realpath(inner)) / "_benzerler"


def test_target_without_root_stays_next_to_file(tmp_path: Path):
    f = write(tmp_path / "x.jpg")
    target = actions.duplicates_target(str(f), [])
    assert Path(target) == Path(os.path.realpath(tmp_path)) / "_benzerler" / "x.jpg"


def test_move_and_undo(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    root = tmp_path / "Foto"
    a = write(root / "Alt" / "A.jpg", b"aaa")
    b = write(root / "B.jpg", b"bb")
    missing = root / "yok.jpg"

    result = actions.move_to_duplicates(db, [normalize_path(a), normalize_path(b), normalize_path(missing)], [str(root)])
    assert len(result.done) == 2 and len(result.failed) == 1
    assert result.done_bytes == 5
    assert not a.exists() and not b.exists()
    moved_a = root / "_benzerler" / "Alt" / "A.jpg"
    assert moved_a.read_bytes() == b"aaa"
    assert (root / "_benzerler" / "B.jpg").exists()

    with Journal(db) as j:
        op = j.last_undoable()
        assert op.id == result.op_id and op.kind == KIND_MOVE
        assert (op.done_count, op.failed_count) == (2, 1)
        assert sorted(it.status for it in j.items(op.id)) == [DONE, DONE, FAILED]

    undo = actions.undo(db, result.op_id)
    assert len(undo.done) == 2 and not undo.failed
    assert a.read_bytes() == b"aaa" and b.read_bytes() == b"bb"
    # Boşalan _benzerler klasörleri kaldırılır, tarama klasörü yerinde kalır
    assert not (root / "_benzerler").exists()
    assert root.is_dir()
    with Journal(db) as j:
        assert j.last_undoable() is None
        assert j.get(result.op_id).undone_at is not None
        assert {it.status for it in j.items(result.op_id)} == {RESTORED, FAILED}


def test_move_never_overwrites(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    root = tmp_path / "Foto"
    write(root / "_benzerler" / "a.jpg", b"eski")
    a = write(root / "a.jpg", b"yeni")
    result = actions.move_to_duplicates(db, [str(a)], [str(root)])
    assert len(result.done) == 1
    assert (root / "_benzerler" / "a.jpg").read_bytes() == b"eski"
    assert (root / "_benzerler" / "a (2).jpg").read_bytes() == b"yeni"


def test_undo_skips_when_original_taken(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    root = tmp_path / "Foto"
    a = write(root / "a.jpg", b"ilk")
    result = actions.move_to_duplicates(db, [str(a)], [str(root)])
    write(a, b"yeni gelen")  # aynı yere başka dosya konmuş

    undo = actions.undo(db, result.op_id)
    assert not undo.done and len(undo.failed) == 1
    assert a.read_bytes() == b"yeni gelen"  # üzerine yazılmadı
    assert (root / "_benzerler" / "a.jpg").read_bytes() == b"ilk"
    with Journal(db) as j:
        op = j.get(result.op_id)
        assert op.undoable  # sorun giderilince yeniden denenebilir
        assert j.items(op.id)[0].status == RESTORE_FAILED

    a.unlink()
    assert len(actions.undo(db, result.op_id).done) == 1
    assert a.read_bytes() == b"ilk"


def test_trash_refused_off_windows_or_on_unsupported_drive(tmp_path: Path):
    if sys.platform == "win32":
        assert recycle.is_trash_supported(str(tmp_path / "x.jpg")) in (True, False)
        assert not recycle.is_trash_supported(r"\\sunucu\paylasim\x.jpg")
    else:
        assert not recycle.is_trash_supported(str(tmp_path / "x.jpg"))


@pytest.mark.skipif(sys.platform != "win32", reason="Geri Dönüşüm Kutusu yalnızca Windows'ta")
def test_trash_and_restore(tmp_path: Path):
    if not recycle.is_trash_supported(str(tmp_path)):
        pytest.skip("Geçici klasör sabit bir sürücüde değil")
    db = tmp_path / "db.sqlite"
    f = write(tmp_path / "Foto" / "Çöpe_Gidecek.jpg", b"kutu testi")
    result = actions.send_to_trash(db, [normalize_path(f)])
    assert result.done == [normalize_path(f)] and not result.failed
    assert not f.exists()
    entry = recycle.find_in_recycle_bin(str(f))
    assert entry is not None and os.path.normcase(entry.original) == os.path.normcase(str(f))

    with Journal(db) as j:
        assert j.last_undoable().kind == KIND_TRASH
    undo = actions.undo(db, result.op_id)
    assert len(undo.done) == 1 and not undo.failed
    assert f.read_bytes() == b"kutu testi"
    assert f.name in os.listdir(f.parent)  # ad yazımı korunur
    assert recycle.find_in_recycle_bin(str(f)) is None
