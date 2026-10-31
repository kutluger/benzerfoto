"""Testlerde kullanılan yardımcılar: sahte fotoğraf üretimi."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter


def make_scene(seed: int = 0, size=(800, 600), shift: int = 0, blur: float = 0.0) -> Image.Image:
    """Tekrarlanabilir bir "fotoğraf" üretir. `shift` ile sahnedeki kişi hafifçe kayar."""
    rng = np.random.default_rng(seed)
    w, h = size
    # Gökyüzü gradyanı + gürültü
    grad = np.linspace(0, 1, h)[:, None]
    base = rng.integers(40, 200, 3)
    arr = (base[None, None, :] * (0.6 + 0.4 * grad[..., None])).repeat(w, axis=1)
    arr = arr + rng.normal(0, 6, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)
    # Zemin ve birkaç nesne
    draw.rectangle([0, int(h * 0.7), w, h], fill=tuple(int(c) for c in rng.integers(20, 120, 3)))
    for _ in range(6):
        x, y = rng.integers(0, w - 80), rng.integers(0, int(h * 0.7))
        draw.ellipse([x, y, x + 60, y + 60], fill=tuple(int(c) for c in rng.integers(0, 255, 3)))
    # "Kişi": kaydırılabilir dikdörtgen
    px = int(w * 0.45) + shift
    draw.rectangle([px, int(h * 0.4), px + 50, int(h * 0.75)], fill=(200, 40, 40))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img


def save_jpeg(img: Image.Image, path: Path, taken_at: str | None = None, model: str | None = None, quality: int = 92) -> Path:
    """JPEG olarak kaydeder; istenirse EXIF çekim zamanı ve cihaz modeli ekler."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if model:
        exif[272] = model
    if taken_at:
        exif.get_ifd(0x8769)[36867] = taken_at
    img.save(path, "JPEG", quality=quality, exif=exif.tobytes())
    return path


@pytest.fixture
def photo_dir(tmp_path: Path) -> Path:
    """Küçük bir örnek arşiv oluşturur."""
    root = tmp_path / "arsiv"
    save_jpeg(make_scene(1), root / "2025" / "IMG_0001.jpg", "2025:08:14 18:42:03", "iPhone 14 Pro")
    save_jpeg(make_scene(1, shift=6), root / "2025" / "IMG_0002.jpg", "2025:08:14 18:42:09", "iPhone 14 Pro")
    save_jpeg(make_scene(2), root / "2025" / "IMG_0003.JPG")
    (root / "diger").mkdir(parents=True)
    make_scene(3).save(root / "diger" / "ekran.png")
    (root / "notlar.txt").write_text("fotoğraf değil")
    return root
