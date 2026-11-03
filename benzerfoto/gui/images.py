"""Fotoğrafları Qt'nin gösterebileceği QImage'a çevirme ve küçük resim önbelleği.

Görüntüler Pillow ile açılır; böylece HEIC desteği ve EXIF yönü taramayla
aynı şekilde çalışır. Çözme işi arka plandaki iş parçacıklarında yapılır,
arayüz donmaz.
"""

from __future__ import annotations

from collections import OrderedDict

from PIL import Image, ImageOps
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

import benzerfoto.features  # noqa: F401  (HEIC açıcısını kaydeder)


def load_qimage(path: str, max_side: int | None = None) -> QImage:
    """Dosyayı açar, EXIF yönünü uygular ve istenirse küçültür."""
    with Image.open(path) as img:
        if max_side:
            img.draft("RGB", (max_side, max_side))
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
        return qimg.copy()  # verinin sahipliğini QImage'a geçir


class _LoadSignals(QObject):
    done = Signal(str, QImage)


class _LoadTask(QRunnable):
    def __init__(self, path: str, max_side: int, signals: _LoadSignals):
        super().__init__()
        self.path, self.max_side, self.signals = path, max_side, signals

    def run(self) -> None:
        try:
            image = load_qimage(self.path, self.max_side)
        except Exception:
            image = QImage()  # okunamadı: boş görüntü
        self.signals.done.emit(self.path, image)


class ThumbnailCache(QObject):
    """Küçük resimleri arka planda yükler ve bellekte saklar (en son kullanılan N tane)."""

    loaded = Signal(str)

    def __init__(self, size: int = 280, limit: int = 1500, parent: QObject | None = None):
        super().__init__(parent)
        self.size = size
        self.limit = limit
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._pending: set[str] = set()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)
        self._signals = _LoadSignals()
        self._signals.done.connect(self._on_done)

    def get(self, path: str) -> QPixmap | None:
        """Hazırsa küçük resmi döndürür; değilse yüklemeyi başlatır ve None döner."""
        pix = self._cache.get(path)
        if pix is not None:
            self._cache.move_to_end(path)
            return pix
        if path not in self._pending:
            self._pending.add(path)
            self._pool.start(_LoadTask(path, self.size, self._signals))
        return None

    def clear_pending(self) -> None:
        """Henüz başlamamış yüklemeleri iptal eder (grup değişince)."""
        self._pool.clear()
        self._pending.clear()

    def _on_done(self, path: str, image: QImage) -> None:
        self._pending.discard(path)
        self._cache[path] = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
        while len(self._cache) > self.limit:
            self._cache.popitem(last=False)
        self.loaded.emit(path)
