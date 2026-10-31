"""Tek bir fotoğraftan karşılaştırma için gereken özellikleri çıkarır.

Her dosya bir kez açılır ve şunlar hesaplanır:
- içerik hash'i (birebir kopya tespiti için)
- algısal hash'ler pHash ve dHash (benzer görüntü tespiti için)
- çözünürlük, EXIF çekim zamanı ve cihaz modeli
- netlik skoru (Laplacian varyansı; grubun en iyisini önermek için)

Bu modüldeki fonksiyonlar ayrı süreçlerde (multiprocessing) çalışır, bu yüzden
yalnızca seri hale getirilebilen (pickle) veri alıp döndürürler.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

import imagehash
import numpy as np
from PIL import Image, ImageOps

from benzerfoto.config import HASH_CHUNK_SIZE, SHARPNESS_LONG_EDGE
from benzerfoto.discovery import FileEntry

try:
    # HEIC/HEIF desteğini Pillow'a ekler (iPhone fotoğrafları)
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:  # pragma: no cover - kurulum eksikse HEIC dosyaları hata kaydı alır
    HEIF_AVAILABLE = False

# Çok büyük panoramalarda Pillow'un "decompression bomb" uyarısını kapat;
# dosyalar kullanıcının kendi arşivinden geliyor.
Image.MAX_IMAGE_PIXELS = None

# EXIF etiket numaraları
_EXIF_IFD = 0x8769
_TAG_DATETIME_ORIGINAL = 36867
_TAG_DATETIME = 306
_TAG_MODEL = 272
_TAG_ORIENTATION = 274


@dataclass
class ImageFeatures:
    """Bir fotoğraf için hesaplanan ve önbellekte saklanan özellikler."""

    path: str
    size: int
    mtime_ns: int
    content_hash: str | None = None
    width: int | None = None
    height: int | None = None
    phash: str | None = None
    dhash: str | None = None
    taken_at: str | None = None  # ISO 8601, örn. "2025-08-14T18:42:17"
    camera: str | None = None
    sharpness: float | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def compute_content_hash(path: str) -> str:
    """Dosyanın tüm içeriğinden BLAKE2b hash'i hesaplar (hızlı ve güvenilir)."""
    hasher = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_exif_datetime(value: object) -> str | None:
    """EXIF tarih metnini ("2025:08:14 18:42:17") ISO biçimine çevirir."""
    if not isinstance(value, str):
        return None
    text = value.strip().rstrip("\x00")
    try:
        return datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def laplacian_variance(gray: np.ndarray) -> float:
    """Gri tonlu görüntünün Laplacian varyansını hesaplar.

    Kenarlar keskinse Laplacian değerleri geniş bir aralığa yayılır ve varyans
    yüksek çıkar; bulanık fotoğrafta düşük çıkar. OpenCV'deki
    `cv2.Laplacian(img, cv2.CV_64F).var()` ile aynı 3x3 çekirdeği kullanır,
    ancak OpenCV bağımlılığı gerektirmez (EXE boyutu küçük kalır).
    """
    g = gray.astype(np.float64)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = (
        g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1]
    )
    return float(lap.var())


def _read_exif(img: Image.Image) -> tuple[str | None, str | None, int]:
    """Çekim zamanı, cihaz modeli ve yön bilgisini okur."""
    try:
        exif = img.getexif()
    except Exception:
        return None, None, 1
    taken_at = None
    try:
        taken_at = parse_exif_datetime(exif.get_ifd(_EXIF_IFD).get(_TAG_DATETIME_ORIGINAL))
    except Exception:
        pass
    if taken_at is None:
        taken_at = parse_exif_datetime(exif.get(_TAG_DATETIME))
    model = exif.get(_TAG_MODEL)
    camera = (model.strip().rstrip("\x00") or None) if isinstance(model, str) else None
    orientation = exif.get(_TAG_ORIENTATION, 1)
    return taken_at, camera, orientation if isinstance(orientation, int) else 1


def extract_features(entry: FileEntry) -> ImageFeatures:
    """Bir dosyanın tüm özelliklerini hesaplar. Hata olursa `error` alanı dolar."""
    result = ImageFeatures(path=entry.path, size=entry.size, mtime_ns=entry.mtime_ns)
    try:
        result.content_hash = compute_content_hash(entry.path)

        with Image.open(entry.path) as img:
            width, height = img.size
            result.taken_at, result.camera, orientation = _read_exif(img)
            # EXIF yönü 5-8 ise fotoğraf 90° döndürülmüş gösterilir; en/boy yer değiştirir
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            result.width, result.height = width, height

            # JPEG'lerde küçültülmüş çözme (draft) çok daha hızlıdır
            img.draft("RGB", (SHARPNESS_LONG_EDGE, SHARPNESS_LONG_EDGE))
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((SHARPNESS_LONG_EDGE, SHARPNESS_LONG_EDGE), Image.Resampling.LANCZOS)

            result.phash = str(imagehash.phash(img))
            result.dhash = str(imagehash.dhash(img))
            result.sharpness = round(laplacian_variance(np.asarray(img.convert("L"))), 2)
    except Exception as exc:  # bozuk ya da okunamayan dosya
        result.error = f"{type(exc).__name__}: {exc}"
    return result
