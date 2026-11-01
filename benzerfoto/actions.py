"""Dosya işlemleri: `_benzerler` klasörüne taşıma, Geri Dönüşüm Kutusu, geri alma.

Hiçbir dosya kalıcı olarak silinmez. Her işlem günlüğe yazılır ve geri
alınabilir. Yollar arayüze önbellekteki biçimiyle (normalize edilmiş, Windows'ta
küçük harf) döner; diskte ise dosya adlarının özgün yazımı korunur.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from benzerfoto import recycle
from benzerfoto.config import DUPLICATES_FOLDER_NAME
from benzerfoto.discovery import is_under, normalize_path
from benzerfoto.journal import (
    DONE,
    FAILED,
    KIND_MOVE,
    KIND_TRASH,
    RESTORE_FAILED,
    RESTORED,
    Journal,
)

# Günlüğe toplu yazma aralığı: çökme olursa en fazla bu kadar kayıt kaybolur
_COMMIT_EVERY = 50

Progress = Callable[[int, int], None]


@dataclass
class ActionResult:
    op_id: int | None = None
    done: list[str] = field(default_factory=list)  # normalize edilmiş yollar
    failed: list[tuple[str, str]] = field(default_factory=list)  # (yol, hata)
    done_bytes: int = 0


def _real(path: str) -> str:
    """Dosyanın diskteki gerçek yazımı (büyük/küçük harf korunur)."""
    return os.path.realpath(path)


def _unique(path: str) -> str:
    """Hedefte aynı adlı dosya varsa "ad (2).jpg" biçiminde boş bir ad bulur."""
    if not os.path.lexists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.lexists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


def duplicates_target(path: str, roots: Iterable[str]) -> str:
    """Taşınacak dosyanın `_benzerler` içindeki hedef yolu.

    Dosya, içinde bulunduğu tarama klasörünün `_benzerler` alt klasörüne alt
    klasör yapısı korunarak taşınır: D:\\Foto\\2020\\a.jpg → D:\\Foto\\_benzerler\\2020\\a.jpg
    Tarama klasörü bilinmiyorsa dosyanın kendi klasöründe `_benzerler` açılır.
    """
    real = _real(path)
    norm = normalize_path(real)
    best_root = None
    for root in roots:
        r = normalize_path(root)
        if is_under(norm, r) and norm != r and (best_root is None or len(r) > len(normalize_path(best_root))):
            best_root = root
    if best_root is None:
        return os.path.join(os.path.dirname(real), DUPLICATES_FOLDER_NAME, os.path.basename(real))
    real_root = _real(best_root)
    return os.path.join(real_root, DUPLICATES_FOLDER_NAME, os.path.relpath(real, real_root))


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def move_to_duplicates(
    db_path: str | os.PathLike, paths: Iterable[str], roots: Iterable[str], progress: Progress | None = None
) -> ActionResult:
    """Dosyaları `_benzerler` klasörlerine taşır ve günlüğe yazar."""
    paths, roots = list(paths), list(roots)
    result = ActionResult()
    with Journal(db_path) as journal:
        result.op_id = journal.start(KIND_MOVE)
        for i, path in enumerate(paths, 1):
            src = _real(path)
            size = _size(src)
            try:
                if not os.path.isfile(src):
                    raise FileNotFoundError("Dosya bulunamadı")
                dst = _unique(duplicates_target(src, roots))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)  # aynı sürücü: anında, içerik kopyalanmaz
            except OSError as exc:
                journal.add_item(result.op_id, src, None, size, FAILED, _error_text(exc))
                result.failed.append((normalize_path(path), _error_text(exc)))
            else:
                journal.add_item(result.op_id, src, dst, size, DONE)
                result.done.append(normalize_path(path))
                result.done_bytes += size
            if i % _COMMIT_EVERY == 0:
                journal.commit()
            if progress:
                progress(i, len(paths))
        journal.commit()
    return result


def send_to_trash(db_path: str | os.PathLike, paths: Iterable[str], progress: Progress | None = None) -> ActionResult:
    """Dosyaları Geri Dönüşüm Kutusu'na gönderir ve günlüğe yazar."""
    paths = list(paths)
    result = ActionResult()
    with Journal(db_path) as journal:
        result.op_id = journal.start(KIND_TRASH)
        step = 200
        for start in range(0, len(paths), step):
            chunk = paths[start : start + step]
            real = {p: _real(p) for p in chunk}
            sizes = {p: _size(real[p]) for p in chunk}
            outcome = recycle.send_to_recycle_bin(list(real.values()))
            for p in chunk:
                error = outcome.get(real[p], "Bilinmeyen hata")
                if error is None:
                    journal.add_item(result.op_id, real[p], None, sizes[p], DONE)
                    result.done.append(normalize_path(p))
                    result.done_bytes += sizes[p]
                else:
                    journal.add_item(result.op_id, real[p], None, sizes[p], FAILED, error)
                    result.failed.append((normalize_path(p), error))
            journal.commit()
            if progress:
                progress(min(start + step, len(paths)), len(paths))
    return result


def undo(db_path: str | os.PathLike, op_id: int, progress: Progress | None = None) -> ActionResult:
    """Bir işlemi geri alır: dosyalar özgün yerlerine döner.

    Özgün yerde aynı adlı dosya varsa üzerine yazılmaz, o dosya atlanır.
    Tüm dosyalar dönerse işlem "geri alındı" olarak işaretlenir; dönmeyenler
    için geri alma daha sonra tekrar denenebilir.
    """
    result = ActionResult(op_id=op_id)
    with Journal(db_path) as journal:
        op = journal.get(op_id)
        if op is None:
            raise ValueError(f"İşlem bulunamadı: {op_id}")
        items = [it for it in journal.items(op_id) if it.status in (DONE, RESTORE_FAILED)]
        for i, it in enumerate(items, 1):
            try:
                if op.kind == KIND_MOVE:
                    _restore_move(it.src, it.dst)
                elif op.kind == KIND_TRASH:
                    recycle.restore_from_recycle_bin(it.src, since=op.created_ts)
                else:
                    raise ValueError(f"Bilinmeyen işlem türü: {op.kind}")
            except (OSError, ValueError) as exc:
                journal.set_item_status(it.rowid, RESTORE_FAILED, _error_text(exc))
                result.failed.append((normalize_path(it.src), _error_text(exc)))
            else:
                journal.set_item_status(it.rowid, RESTORED)
                result.done.append(normalize_path(it.src))
                result.done_bytes += it.size
            if i % _COMMIT_EVERY == 0:
                journal.commit()
            if progress:
                progress(i, len(items))
        journal.commit()
        if not result.failed:
            journal.mark_undone(op_id)
    return result


def _restore_move(src: str, dst: str | None) -> None:
    if not dst or not os.path.isfile(dst):
        raise FileNotFoundError("_benzerler içindeki dosya bulunamadı (taşınmış ya da silinmiş olabilir)")
    if os.path.lexists(src):
        raise FileExistsError("Özgün yerde aynı adlı bir dosya var")
    os.makedirs(os.path.dirname(src), exist_ok=True)
    os.rename(dst, src)
    _remove_empty_dirs(os.path.dirname(dst))


def _remove_empty_dirs(folder: str) -> None:
    """Geri alma sonrası boşalan klasörleri `_benzerler` dahil yukarı doğru kaldırır.

    Yalnızca boş klasörler kaldırılır (os.rmdir boş olmayan klasörü silmez) ve
    `_benzerler` klasörünün dışına çıkılmaz.
    """
    parts = os.path.normcase(folder).split(os.sep)
    if DUPLICATES_FOLDER_NAME not in parts:
        return
    stop = len(parts) - parts[::-1].index(DUPLICATES_FOLDER_NAME) - 1  # _benzerler'in konumu
    current = folder
    for _ in range(len(parts) - stop):
        try:
            os.rmdir(current)
        except OSError:
            return
        current = os.path.dirname(current)


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, PermissionError):
        return "Erişim engellendi (dosya başka bir programda açık olabilir)"
    if isinstance(exc, FileExistsError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    if isinstance(exc, FileNotFoundError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return getattr(exc, "strerror", None) or str(exc) or type(exc).__name__
