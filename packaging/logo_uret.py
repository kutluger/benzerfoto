r"""BF logosunun PNG ve ICO dosyalarını SVG kaynağından üretir.

Kullanım (proje klasöründe):
    .venv\Scripts\python packaging\logo_uret.py

Girdi:  benzerfoto/assets/bf-logo.svg
Çıktı:  benzerfoto/assets/bf-<boyut>.png (pencere simgesi)
        benzerfoto/assets/bf.ico           (EXE ve görev çubuğu simgesi, 16-256 px)
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "benzerfoto" / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def render(renderer: QSvgRenderer, size: int) -> Image.Image:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(ASSETS / "bf-logo.svg"))
    if not renderer.isValid():
        print("SVG okunamadı")
        return 1
    images = {size: render(renderer, size) for size in SIZES}
    for size in (16, 24, 32, 48, 64, 128, 256):
        images[size].save(ASSETS / f"bf-{size}.png")
    # Her boyut ayrı çizilir: küçük boyutlar büyük resmin küçültülmüşünden daha net olur
    largest = images[SIZES[-1]]
    largest.save(
        ASSETS / "bf.ico",
        sizes=[(s, s) for s in SIZES],
        append_images=[images[s] for s in SIZES[:-1]],
    )
    print(f"Hazır: {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
