"""Klasörlerde gezinip desteklenen fotoğraf dosyalarını bulur."""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from benzerfoto.config import DUPLICATES_FOLDER_NAME, SUPPORTED_EXTENSIONS


@dataclass(frozen=True)
class FileEntry:
    """Diskte bulunan bir dosyanın önbellek kontrolü için gereken bilgileri."""

    path: str
    size: int
    mtime_ns: int


def normalize_path(path: str | os.PathLike) -> str:
    """Yolu mutlak ve karşılaştırılabilir hale getirir.

    Windows büyük/küçük harf ayırmadığı için normcase uygulanır; böylece
    "D:\\Foto" ile "d:\\foto" aynı klasör sayılır.
    """
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def is_under(path: str, folder: str) -> bool:
    """`path`, `folder` klasörünün kendisi ya da altında mı? (İkisi de normalize edilmiş olmalı.)"""
    if path == folder:
        return True
    prefix = folder if folder.endswith(os.sep) else folder + os.sep
    return path.startswith(prefix)


def iter_image_files(
    roots: Iterable[str | os.PathLike],
    excludes: Iterable[str | os.PathLike] = (),
    recursive: bool = True,
    extensions: frozenset[str] = SUPPORTED_EXTENSIONS,
) -> Iterator[FileEntry]:
    """Verilen kök klasörlerdeki fotoğraf dosyalarını tek tek döndürür.

    - Hariç tutulan klasörler ve `_benzerler` klasörleri atlanır.
    - İç içe verilen kök klasörlerde aynı dosya iki kez döndürülmez.
    - Erişim izni olmayan klasörler sessizce atlanır.
    """
    exclude_list = [normalize_path(e) for e in excludes]
    seen_dirs: set[str] = set()

    for root in roots:
        stack = [normalize_path(root)]
        while stack:
            current = stack.pop()
            if current in seen_dirs:
                continue
            seen_dirs.add(current)
            if any(is_under(current, ex) for ex in exclude_list):
                continue

            try:
                with os.scandir(current) as it:
                    entries = list(it)
            except OSError:
                continue

            # Sıralı gezinme, ilerleme çubuğunun ve testlerin tutarlı olmasını sağlar
            entries.sort(key=lambda e: e.name.lower())
            subdirs: list[str] = []
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if recursive and entry.name.lower() != DUPLICATES_FOLDER_NAME:
                            subdirs.append(normalize_path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    if os.path.splitext(entry.name)[1].lower() not in extensions:
                        continue
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                yield FileEntry(normalize_path(entry.path), st.st_size, st.st_mtime_ns)

            # Yığından ters sırada çıkacakları için alfabetik sırayı korumak üzere ters ekle
            stack.extend(reversed(subdirs))
