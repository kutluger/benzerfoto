"""Arayüz bileşenleri: grup listesi, küçük resim kartları, ızgara ve büyük önizleme."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from benzerfoto.features import ImageFeatures
from benzerfoto.formatting import format_date, format_size, format_time
from benzerfoto.grouping import GroupKind, PhotoGroup
from benzerfoto.gui.images import ThumbnailCache
from benzerfoto.gui.style import ACCENT, OK, TAG_COLORS


def group_title(group: PhotoGroup) -> str:
    """Grup listesinde görünecek başlık."""
    first = group.members[0]
    if group.kind == GroupKind.SCENE:
        return format_date(first.taken_at)
    name = Path(first.path).name
    if group.kind == GroupKind.EXACT:
        return f"{name} ×{len(group.members)}"
    formats = sorted({Path(m.path).suffix.upper().lstrip(".") for m in group.members})
    return f"{Path(name).stem} ({' + '.join(formats)})" if len(formats) > 1 else name


def scene_time_range(group: PhotoGroup) -> str:
    times = [m.taken_at for m in group.members if m.taken_at]
    if not times:
        return ""
    return f"{format_date(min(times))[:-6]} {format_time(min(times))} – {format_time(max(times))}"


# ---------------------------------------------------------------------------
# Orta panel: grup listesi (binlerce grup için model + çizici)
# ---------------------------------------------------------------------------


class GroupListModel(QAbstractListModel):
    GroupRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups: list[PhotoGroup] = []

    def set_groups(self, groups: list[PhotoGroup]) -> None:
        self.beginResetModel()
        self.groups = groups
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt adı)
        return 0 if parent.isValid() else len(self.groups)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        group = self.groups[index.row()]
        if role == self.GroupRole:
            return group
        if role == Qt.ItemDataRole.DisplayRole:
            return group_title(group)
        return None

    def refresh_row(self, row: int) -> None:
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)


class GroupDelegate(QStyledItemDelegate):
    """Her grubu küçük resim, başlık, alt bilgi ve tür etiketiyle çizer."""

    ROW_HEIGHT = 64
    THUMB = 46

    def __init__(self, thumbs: ThumbnailCache, parent=None):
        super().__init__(parent)
        self.thumbs = thumbs

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(300, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        group: PhotoGroup = index.data(GroupListModel.GroupRole)
        r = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(r, QColor("#eef4ff") if selected else QColor("white"))
        if selected:
            painter.fillRect(QRect(r.left(), r.top(), 3, r.height()), QColor(ACCENT))
        elif group.reviewed:
            painter.fillRect(QRect(r.left(), r.top(), 3, r.height()), QColor(OK))
        painter.setPen(QColor("#f0f0f0"))
        painter.drawLine(r.bottomLeft(), r.bottomRight())

        # Küçük resim (grubun önerilen fotoğrafı)
        thumb_rect = QRect(r.left() + 14, r.top() + (r.height() - self.THUMB) // 2, self.THUMB, self.THUMB)
        best = group.best or group.members[0]
        pix = self.thumbs.get(best.path)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(thumb_rect), 4, 4)
        painter.setClipPath(clip)
        painter.fillRect(thumb_rect, QColor("#e5e7eb"))
        if pix is not None and not pix.isNull():
            scaled = pix.scaled(thumb_rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - thumb_rect.width()) // 2
            sy = (scaled.height() - thumb_rect.height()) // 2
            painter.drawPixmap(thumb_rect, scaled, QRect(sx, sy, thumb_rect.width(), thumb_rect.height()))
        painter.setClipping(False)

        # Tür etiketi (sağda)
        bg, fg = TAG_COLORS[group.kind.value]
        tag_font = QFont(option.font)
        tag_font.setPointSizeF(max(7.0, option.font.pointSizeF() - 2))
        tag_font.setBold(True)
        painter.setFont(tag_font)
        label = group.kind.label.upper()
        tw = painter.fontMetrics().horizontalAdvance(label) + 14
        tag_rect = QRect(r.right() - tw - 14, r.center().y() - 9, tw, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(tag_rect, 9, 9)
        painter.setPen(QColor(fg))
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, label)

        # Başlık ve alt bilgi
        text_left = thumb_rect.right() + 10
        text_width = tag_rect.left() - text_left - 8
        title_font = QFont(option.font)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#1f2328"))
        title = painter.fontMetrics().elidedText(group_title(group), Qt.TextElideMode.ElideRight, text_width)
        painter.drawText(QRect(text_left, r.top() + 12, text_width, 20), Qt.AlignmentFlag.AlignLeft, title)

        painter.setFont(option.font)
        painter.setPen(QColor("#666666"))
        sub = f"{len(group.members)} dosya · {format_size(group.total_size)}"
        if group.marked:
            sub += f" · {len(group.marked)} işaretli"
        sub_rect = QRect(text_left, r.top() + 33, text_width, 20)
        if group.reviewed:
            # Yeşil "✓ İncelendi" önde, ayrıntılar arkasında
            done = "✓ İncelendi  "
            painter.setPen(QColor(OK))
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft, done)
            shift = painter.fontMetrics().horizontalAdvance(done)
            sub_rect.adjust(shift, 0, 0, 0)
            painter.setPen(QColor("#666666"))
        sub = painter.fontMetrics().elidedText(sub, Qt.TextElideMode.ElideRight, sub_rect.width())
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft, sub)
        painter.restore()


# ---------------------------------------------------------------------------
# Sağ panel: küçük resim kartı ve ızgara
# ---------------------------------------------------------------------------


class ThumbCard(QFrame):
    """Bir fotoğrafın kartı: resim, işaret kutusu, ★, dosya bilgileri, netlik çubuğu."""

    IMAGE_W, IMAGE_H = 220, 150

    clicked = Signal(str)
    mark_toggled = Signal(str, bool)
    keep_requested = Signal(str)  # "bunu tut" (öneri yap)
    open_folder_requested = Signal(str)
    discard_group_requested = Signal()  # grubun tamamını gönder

    def __init__(self, item: ImageFeatures, group: PhotoGroup, max_sharpness: float, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("card")
        self.setFixedWidth(self.IMAGE_W + 2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 6)
        layout.setSpacing(2)

        self.image = QLabel()
        self.image.setObjectName("cardImage")
        self.image.setFixedSize(self.IMAGE_W, self.IMAGE_H)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image)

        # Resmin üstündeki işaret kutusu ve rozetler
        self.mark_box = QCheckBox(self.image)
        self.mark_box.setObjectName("markBox")
        self.mark_box.move(8, 8)
        self.mark_box.toggled.connect(lambda on: self.mark_toggled.emit(self.item.path, on))

        self.badge = QLabel(self.image)
        self.badge.hide()

        info = QVBoxLayout()
        info.setContentsMargins(8, 4, 8, 0)
        info.setSpacing(1)
        name = QLabel(Path(item.path).name)
        name.setObjectName("cardName")
        name.setToolTip(item.path)
        info.addWidget(name)
        # Aynı adlı kopyaları ayırt etmek için klasör adı
        parent = Path(item.path).parent
        folder = QLabel()
        folder.setObjectName("cardMeta")
        folder.setToolTip(str(parent))
        folder.setText(folder.fontMetrics().elidedText(f"📁 {parent.name}", Qt.TextElideMode.ElideMiddle, self.IMAGE_W - 16))
        info.addWidget(folder)
        res = f"{item.width}×{item.height}" if item.width else "?"
        meta = QLabel(f"{res} · {format_size(item.size)} · {format_time(item.taken_at)}")
        meta.setObjectName("cardMeta")
        info.addWidget(meta)

        sharp_row = QHBoxLayout()
        sharp_row.setSpacing(6)
        lbl = QLabel("Netlik")
        lbl.setObjectName("cardMeta")
        sharp_row.addWidget(lbl)
        bar = QProgressBar()
        bar.setObjectName("sharpBar")
        bar.setTextVisible(False)
        bar.setFixedHeight(4)
        bar.setRange(0, 100)
        ratio = (item.sharpness or 0) / max_sharpness if max_sharpness else 0
        bar.setValue(int(ratio * 100))
        bar.setProperty("level", "low" if ratio < 0.5 else "mid" if ratio < 0.75 else "high")
        sharp_row.addWidget(bar, 1)
        val = QLabel(f"{item.sharpness:.0f}" if item.sharpness is not None else "—")
        val.setObjectName("cardMeta")
        sharp_row.addWidget(val)
        info.addLayout(sharp_row)
        if not item.ok:
            err = QLabel("⚠ Okunamadı")
            err.setObjectName("cardMeta")
            err.setToolTip(item.error or "")
            info.addWidget(err)
        layout.addLayout(info)

        self.update_state(group)

    def update_state(self, group: PhotoGroup, focused: bool | None = None) -> None:
        """İşaret, ★ ve koruma durumunu gruba göre günceller."""
        is_best = group.best_path == self.item.path
        protected = self.item.path in group.protected
        self.mark_box.blockSignals(True)
        self.mark_box.setChecked(self.item.path in group.marked)
        self.mark_box.setEnabled(not protected)
        self.mark_box.setToolTip("Korunan klasörde, işaretlenemez" if protected else "Ayrılacaklar listesine ekle/çıkar")
        self.mark_box.blockSignals(False)

        if protected:
            self.badge.setObjectName("shieldBadge")
            self.badge.setText("🛡 Korunuyor")
        elif is_best:
            self.badge.setObjectName("starBadge")
            self.badge.setText("★ Önerilen")
        self.badge.setVisible(protected or is_best)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.badge.adjustSize()
        self.badge.move(self.IMAGE_W - self.badge.width() - 8, 7)

        self.setProperty("best", is_best)
        if focused is not None:
            self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_pixmap(self, pix: QPixmap | None) -> None:
        if pix is None:
            self.image.setText("Yükleniyor…")
        elif pix.isNull():
            self.image.setText("Önizleme yok")
        else:
            self.image.setPixmap(
                pix.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item.path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.mark_box.isEnabled():
            self.mark_box.toggle()

    def _show_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        keep = menu.addAction("★ Bunu tut, diğerlerini işaretle")
        folder = menu.addAction("📂 Dosya konumunu aç")
        menu.addSeparator()
        discard = menu.addAction("🗑 Grubun tamamını Geri Dönüşüm Kutusu'na gönder…")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == keep:
            self.keep_requested.emit(self.item.path)
        elif chosen == folder:
            self.open_folder_requested.emit(self.item.path)
        elif chosen == discard:
            self.discard_group_requested.emit()


class ThumbnailGrid(QScrollArea):
    """Seçili grubun kartlarını pencere genişliğine göre sütunlara dizer."""

    card_clicked = Signal(str)
    mark_toggled = Signal(str, bool)
    keep_requested = Signal(str)
    open_folder_requested = Signal(str)
    discard_group_requested = Signal()

    SPACING = 12

    def __init__(self, thumbs: ThumbnailCache, parent=None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        # Seçicisiz "background: transparent" alt pencerelere de geçer; kartların
        # sağ tık menüsü de saydam olup siyah kutu gibi görünüyordu.
        self._container.setObjectName("gridContainer")
        self._container.setStyleSheet("QWidget#gridContainer { background: transparent; }")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(16, 14, 16, 14)
        self._grid.setSpacing(self.SPACING)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._container)
        self.cards: dict[str, ThumbCard] = {}
        self._columns = 0
        self.thumbs.loaded.connect(self._on_thumb_loaded)

    def show_group(self, group: PhotoGroup | None, focused_path: str | None) -> None:
        for card in self.cards.values():
            # deleteLater olay döngüsünü bekler; o ana kadar eski kart görünmesin
            self._grid.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards.clear()
        self.thumbs.clear_pending()
        if group is None:
            return
        max_sharp = max((m.sharpness or 0) for m in group.members)
        for item in group.members:
            card = ThumbCard(item, group, max_sharp)
            card.update_state(group, focused=item.path == focused_path)
            card.set_pixmap(self.thumbs.get(item.path))
            card.clicked.connect(self.card_clicked)
            card.mark_toggled.connect(self.mark_toggled)
            card.keep_requested.connect(self.keep_requested)
            card.open_folder_requested.connect(self.open_folder_requested)
            card.discard_group_requested.connect(self.discard_group_requested)
            self.cards[item.path] = card
        self._columns = 0
        self._relayout()
        self.verticalScrollBar().setValue(0)

    def update_states(self, group: PhotoGroup, focused_path: str | None) -> None:
        for path, card in self.cards.items():
            card.update_state(group, focused=path == focused_path)

    def ensure_visible(self, path: str) -> None:
        """Klavyeyle seçilen kart görünür alanın dışındaysa kaydırır."""
        card = self.cards.get(path)
        if card is not None:
            self.ensureWidgetVisible(card, 16, 16)

    def _relayout(self) -> None:
        width = self.viewport().width() - 32
        columns = max(1, (width + self.SPACING) // (ThumbCard.IMAGE_W + 2 + self.SPACING))
        if columns == self._columns:
            return
        self._columns = columns
        for card in self.cards.values():
            self._grid.removeWidget(card)
        for i, card in enumerate(self.cards.values()):
            self._grid.addWidget(card, i // columns, i % columns)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def _on_thumb_loaded(self, path: str) -> None:
        card = self.cards.get(path)
        if card is not None:
            card.set_pixmap(self.thumbs.get(path))


# ---------------------------------------------------------------------------
# Büyük önizleme
# ---------------------------------------------------------------------------


class ImagePreview(QGraphicsView):
    """Fare tekerleğiyle yakınlaştırılan, sürüklenerek gezilen önizleme.

    Çift tıklama pencereye sığdırır.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewView")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._item)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fit = True
        self._source_width = 0

        self.badge = QLabel(self)
        self.badge.setObjectName("zoomBadge")
        self.badge.move(10, 10)

        self.message = QLabel(self)
        self.message.setStyleSheet("color: #bbbbbb; background: transparent;")
        self.message.hide()

    def set_pixmap(self, pix: QPixmap | None, source_width: int = 0, message: str = "") -> None:
        self._item.setPixmap(pix if pix is not None else QPixmap())
        self._scene.setSceneRect(QRectF(self._item.pixmap().rect()))
        self._source_width = source_width or (pix.width() if pix else 0)
        self.message.setText(message)
        self.message.adjustSize()
        self.message.setVisible(bool(message))
        self._position_overlays()
        self.fit()

    def fit(self) -> None:
        self._fit = True
        if not self._item.pixmap().isNull():
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._update_badge()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._item.pixmap().isNull():
            return
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._fit = False
        self.scale(factor, factor)
        self._update_badge()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.fit()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._fit:
            self.fit()
        self._position_overlays()

    def _position_overlays(self) -> None:
        self.badge.move(10, self.height() - self.badge.height() - 10)
        self.message.move((self.width() - self.message.width()) // 2, (self.height() - self.message.height()) // 2)

    def _update_badge(self) -> None:
        pix_w = self._item.pixmap().width()
        if not pix_w or not self._source_width:
            self.badge.hide()
            return
        # Gösterilen boyutun asıl fotoğraf çözünürlüğüne oranı
        percent = self.transform().m11() * pix_w / self._source_width * 100
        self.badge.setText(f"🔍 %{percent:.0f} · tekerlek ile yakınlaştır · çift tık: sığdır")
        self.badge.adjustSize()
        self.badge.show()
        self._position_overlays()


class DetailsPanel(QWidget):
    """Önizlemedeki fotoğrafın ayrıntıları."""

    ROWS = [
        ("folder", "Klasör"),
        ("resolution", "Çözünürlük"),
        ("size", "Boyut"),
        ("taken", "Çekim"),
        ("camera", "Cihaz"),
        ("sharpness", "Netlik"),
        ("note", "Not"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(270)
        self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)
        head = QHBoxLayout()
        self.name = QLabel()
        self.name.setStyleSheet("font-weight: 600;")
        self.name.setWordWrap(True)
        head.addWidget(self.name, 1)
        self.badge = QLabel()
        head.addWidget(self.badge)
        layout.addLayout(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.values: dict[str, QLabel] = {}
        for row, (key, title) in enumerate(self.ROWS):
            t = QLabel(title)
            t.setObjectName("muted")
            t.setAlignment(Qt.AlignmentFlag.AlignTop)
            v = QLabel("—")
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(t, row, 0)
            grid.addWidget(v, row, 1)
            self.values[key] = v
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

    def show_item(self, item: ImageFeatures | None, group: PhotoGroup | None) -> None:
        if item is None or group is None:
            self.name.setText("")
            self.badge.clear()
            for v in self.values.values():
                v.setText("—")
            return
        self.name.setText(Path(item.path).name)
        if item.path in group.protected:
            self.badge.setObjectName("shieldBadge")
            self.badge.setText("🛡 Korunuyor")
        elif item.path == group.best_path:
            self.badge.setObjectName("starBadge")
            self.badge.setText("★ Önerilen")
        else:
            self.badge.setObjectName("")
            self.badge.setText("İşaretli" if item.path in group.marked else "")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

        best_sharp = max((m.sharpness or 0) for m in group.members)
        sharp = f"{item.sharpness:.0f}" if item.sharpness is not None else "—"
        if item.sharpness is not None and item.sharpness >= best_sharp and len(group.members) > 1:
            sharp += " (grupta en yüksek)"
        note = ""
        if item.path == group.best_path:
            note = "Grubun en iyisi olarak önerildi"
            if group.kind == GroupKind.EXACT:
                note = "İçerikler aynı; asıl klasördeki dosya tutuluyor"
        if not item.ok:
            note = f"Okunamadı: {item.error}"
        self.values["folder"].setText(str(Path(item.path).parent))
        self.values["resolution"].setText(f"{item.width} × {item.height}" if item.width else "—")
        self.values["size"].setText(format_size(item.size))
        self.values["taken"].setText(format_date(item.taken_at) if item.taken_at else "EXIF yok")
        self.values["camera"].setText(item.camera or "—")
        self.values["sharpness"].setText(sharp)
        self.values["note"].setText(note or "—")
