"""Windows Geri Dönüşüm Kutusu: dosya gönderme ve geri yükleme.

Ek paket kullanılmaz; Windows'un kendi SHFileOperationW işlevi çağrılır.
Güvenlik için:
- Yalnızca sabit yerel sürücülerde çalışır. Ağ ve USB sürücülerinde Geri
  Dönüşüm Kutusu yoktur; oralarda Windows dosyayı kalıcı siler.
- FOF_WANTNUKEWARNING bayrağı açıktır: bir dosya kutuya sığmaz ve kalıcı
  silinecek olursa Windows kullanıcıya sorar.

Geri yükleme, kutunun diskteki kaydından ($Recycle.Bin\\<SID>\\$I…/$R…)
yapılır: $I dosyası özgün yolu ve silinme zamanını tutar, $R dosyası asıl
içeriktir. $R özgün yerine taşınır, artık işe yaramayan $I kaydı kaldırılır.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# SHFileOperationW sabitleri
_FO_DELETE = 3
_FOF_SILENT = 0x0004
_FOF_NOCONFIRMATION = 0x0010
_FOF_ALLOWUNDO = 0x0040
_FOF_NOERRORUI = 0x0400
_FOF_WANTNUKEWARNING = 0x4000
_DRIVE_FIXED = 3
_BATCH = 200


def is_trash_supported(path: str) -> bool:
    """Bu dosya Geri Dönüşüm Kutusu'na güvenle gönderilebilir mi?"""
    if sys.platform != "win32":
        return False
    import ctypes

    drive = os.path.splitdrive(os.path.abspath(path))[0]
    if not drive or drive.startswith("\\\\"):
        return False  # ağ yolu (\\sunucu\paylaşım)
    return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == _DRIVE_FIXED


def send_to_recycle_bin(paths: list[str]) -> dict[str, str | None]:
    """Dosyaları Geri Dönüşüm Kutusu'na gönderir.

    Her yol için hata metni döndürür (None: başarılı). Desteklenmeyen
    sürücüdeki dosyalara hiç dokunulmaz.
    """
    if sys.platform != "win32":
        raise OSError("Geri Dönüşüm Kutusu yalnızca Windows'ta destekleniyor")
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", ctypes.c_void_p),
            ("pTo", ctypes.c_void_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    shell = ctypes.windll.shell32
    shell.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell.SHFileOperationW.restype = ctypes.c_int

    results: dict[str, str | None] = {}
    todo = []
    for p in paths:
        if not os.path.isfile(p):
            results[p] = "Dosya bulunamadı"
        elif not is_trash_supported(p):
            results[p] = "Bu sürücüde Geri Dönüşüm Kutusu yok"
        else:
            todo.append(os.path.abspath(p))

    for i in range(0, len(todo), _BATCH):
        batch = todo[i : i + _BATCH]
        # Yollar \0 ile ayrılır, liste \0\0 ile biter
        text = "\0".join(batch) + "\0\0"
        buf = (ctypes.c_wchar * len(text))(*text)
        op = SHFILEOPSTRUCTW()
        op.wFunc = _FO_DELETE
        op.pFrom = ctypes.addressof(buf)
        op.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI | _FOF_WANTNUKEWARNING
        code = shell.SHFileOperationW(ctypes.byref(op))
        for p in batch:
            if not os.path.exists(p):
                results[p] = None
            elif op.fAnyOperationsAborted:
                results[p] = "İşlem kullanıcı tarafından iptal edildi"
            else:
                results[p] = f"Windows hata kodu {code:#x}" if code else "Dosya taşınamadı"
    return results


@dataclass
class TrashEntry:
    info_path: str  # $I… (özgün yol + zaman)
    data_path: str  # $R… (içerik)
    original: str
    deleted_at: float  # Unix zamanı


def _parse_info(path: str) -> tuple[str, float] | None:
    try:
        with open(path, "rb") as f:
            data = f.read(4096)
    except OSError:
        return None
    if len(data) < 24:
        return None
    version = int.from_bytes(data[0:8], "little")
    filetime = int.from_bytes(data[16:24], "little")
    if version == 1:
        raw = data[24 : 24 + 520]
    elif version == 2 and len(data) >= 28:
        n = int.from_bytes(data[24:28], "little")
        raw = data[28 : 28 + n * 2]
    else:
        return None
    name = raw.decode("utf-16-le", errors="replace").split("\0", 1)[0]
    return name, filetime / 10_000_000 - 11_644_473_600


def find_in_recycle_bin(original: str, since: float = 0.0) -> TrashEntry | None:
    """Özgün yolu `original` olan, `since` sonrasında silinmiş en yeni kaydı bulur."""
    original = os.path.abspath(original)
    drive = os.path.splitdrive(original)[0]
    bin_dir = os.path.join(drive + os.sep, "$Recycle.Bin")
    target = os.path.normcase(original)
    best: TrashEntry | None = None
    try:
        sid_dirs = [e.path for e in os.scandir(bin_dir) if e.is_dir()]
    except OSError:
        return None
    for sid_dir in sid_dirs:
        try:
            entries = list(os.scandir(sid_dir))
        except OSError:
            continue  # başka kullanıcının klasörü
        for e in entries:
            if not e.name.upper().startswith("$I"):
                continue
            parsed = _parse_info(e.path)
            if parsed is None or os.path.normcase(parsed[0]) != target:
                continue
            # Saat farklarına karşı küçük bir pay
            if parsed[1] < since - 120:
                continue
            data_path = os.path.join(sid_dir, "$R" + e.name[2:])
            if not os.path.exists(data_path):
                continue
            if best is None or parsed[1] > best.deleted_at:
                best = TrashEntry(e.path, data_path, parsed[0], parsed[1])
    return best


def restore_from_recycle_bin(original: str, since: float = 0.0) -> None:
    """Geri Dönüşüm Kutusu'na gönderilmiş dosyayı özgün yerine geri koyar."""
    entry = find_in_recycle_bin(original, since)
    if entry is None:
        raise FileNotFoundError("Geri Dönüşüm Kutusu'nda bulunamadı (kutu boşaltılmış olabilir)")
    if os.path.exists(entry.original):
        raise FileExistsError("Özgün yerde aynı adlı bir dosya var")
    os.makedirs(os.path.dirname(entry.original), exist_ok=True)
    os.rename(entry.data_path, entry.original)
    try:
        os.remove(entry.info_path)  # yalnızca kutunun kayıt dosyası
    except OSError:
        pass
