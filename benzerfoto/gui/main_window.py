"""Ana pencere: sol panel (klasörler, mod, eşik, TARA), orta panel (gruplar),
sağ panel (küçük resim ızgarası + büyük önizleme), alt çubuk (işaretli dosyalar).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from benzerfoto import __version__, actions, recycle, report, review
from benzerfoto.cache import FeatureCache
from benzerfoto.config import DUPLICATES_FOLDER_NAME, default_db_path
from benzerfoto.features import ImageFeatures
from benzerfoto.formatting import format_count, format_size
from benzerfoto.grouping import (
    GroupKind,
    PhotoGroup,
    build_groups,
    choose_best,
    similarity_to_distance,
)
from benzerfoto.gui.confirm import DiscardGroupDialog
from benzerfoto.gui.history import HistoryDialog
from benzerfoto.gui.icon import app_icon
from benzerfoto.gui.settings_dialog import SettingsDialog, window_text
from benzerfoto.gui.shortcuts_help import ShortcutsDialog
from benzerfoto.gui.images import ThumbnailCache, load_qimage
from benzerfoto.journal import KIND_MOVE, KIND_TRASH, Journal, Operation
from benzerfoto.gui.style import TAG_COLORS
from benzerfoto.gui.tasks import ProgressRelay, ScanThread, run_async
from benzerfoto.gui.widgets import (
    DetailsPanel,
    GroupDelegate,
    GroupListModel,
    ImagePreview,
    ThumbnailGrid,
    scene_time_range,
)
from benzerfoto.settings import WINDOW_CHOICES, AppSettings, migrate_settings

# Klasör listesindeki satır türleri
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
FOLDER_SCAN, FOLDER_EXCLUDE, FOLDER_PROTECT = "scan", "exclude", "protect"
FOLDER_ICONS = {FOLDER_SCAN: "📁", FOLDER_EXCLUDE: "🚫", FOLDER_PROTECT: "🛡"}

FORMATS = [("JPG", (".jpg", ".jpeg")), ("HEIC", (".heic", ".heif")), ("PNG", (".png",)), ("WEBP", (".webp",))]
REPORT_FILTER_HTML = "HTML raporu, küçük resimli (*.html)"
REPORT_FILTER_CSV = "CSV tablosu, Excel için (*.csv)"
SORT_CHOICES = ["En çok yer kazandıran", "En kalabalık", "Tarihe göre (yeni → eski)"]
# Odakta bunlardan biri varken klavye kısayolları devre dışı: kullanıcı yazı yazıyor
TEXT_INPUTS = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)


def section_title(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionTitle")
    return label


class MainWindow(QMainWindow):
    def __init__(self, db_path: Path | None = None, settings: QSettings | None = None):
        super().__init__()
        self.setWindowTitle("BenzerFoto — Benzer ve Kopya Fotoğraf Bulucu")
        self.setWindowIcon(app_icon())
        self.resize(1600, 980)
        self.db_path = Path(db_path) if db_path else default_db_path()
        # Uygulama/kuruluş adı app.py'de "BenzerFoto" olarak verilir; testler
        # geçici bir INI dosyası verip gerçek ayarlara dokunmaz.
        self.settings = settings if settings is not None else QSettings()
        migrate_settings(self.settings)
        self.app_settings = AppSettings.load(self.settings)

        self.features: list[ImageFeatures] = []
        self.groups_by_kind: dict[GroupKind, list[PhotoGroup]] = {k: [] for k in GroupKind}
        self.visible_groups: list[PhotoGroup] = []
        self.current_group: PhotoGroup | None = None
        self.focused_path: str | None = None
        self._shown_group: PhotoGroup | None = None  # sağ panelde en son çizilen grup
        self.scan_thread: ScanThread | None = None
        self._group_request = 0  # eski gruplama sonuçlarını yok saymak için sayaç
        self._preview_request = 0
        # Her modun kendi eşiği (benzerlik yüzdesi); açılışta Ayarlar'daki varsayılanlar
        self.thresholds = {
            GroupKind.SIMILAR: float(self.app_settings.similar_threshold),
            GroupKind.SCENE: float(self.app_settings.scene_threshold),
        }
        self._busy = False  # dosya işlemi sürüyor mu
        self._last_undoable: Operation | None = None
        self._progress_dialog: QProgressDialog | None = None

        self.thumbs = ThumbnailCache(parent=self)
        self._regroup_timer = QTimer(self, singleShot=True, interval=300)
        self._regroup_timer.timeout.connect(self._regroup_current)

        central = QWidget()
        central.setObjectName("centralArea")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_left_panel())
        body.addWidget(self._build_mid_panel())
        body.addWidget(self._build_right_panel(), 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_bottom_bar())
        self.setCentralWidget(central)
        self._build_status_bar()
        self._build_shortcuts()

        self._load_settings()
        self._update_mode_controls()
        self._refresh_undo_state()
        self._show_group(None)

    # ------------------------------------------------------------------
    # Sol panel
    # ------------------------------------------------------------------

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        lay.addWidget(section_title("Klasörler"))
        self.folder_list = QListWidget()
        self.folder_list.setObjectName("folderList")
        self.folder_list.setMaximumHeight(170)
        self.folder_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.folder_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.folder_list.setToolTip("📁 taranır · 🚫 hariç tutulur · 🛡 korunur (asla işaretlenmez)")
        lay.addWidget(self.folder_list)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, kind, tip in [
            ("+ Ekle", FOLDER_SCAN, "Taranacak klasör ekle"),
            ("Hariç tut", FOLDER_EXCLUDE, "Taramaya dahil edilmeyecek bir alt klasör seç"),
            ("Koru", FOLDER_PROTECT, "Bu klasördeki fotoğraflar hiçbir zaman ayrılmak üzere işaretlenmez"),
        ]:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, k=kind: self._add_folder(k))
            row.addWidget(btn)
        remove = QPushButton("Kaldır")
        remove.clicked.connect(self._remove_folder)
        row.addWidget(remove)
        lay.addLayout(row)
        self.recursive_box = QCheckBox("Alt klasörleri de tara")
        self.recursive_box.setChecked(True)
        lay.addWidget(self.recursive_box)

        lay.addSpacing(8)
        lay.addWidget(section_title("Bulma modu"))
        self.mode_group = QButtonGroup(self)
        self.mode_buttons: dict[GroupKind, QRadioButton] = {}
        for i, kind in enumerate([GroupKind.EXACT, GroupKind.SIMILAR, GroupKind.SCENE]):
            btn = QRadioButton({GroupKind.EXACT: "Birebir kopya", GroupKind.SIMILAR: "Benzer görüntü", GroupKind.SCENE: "Aynı sahne"}[kind])
            self.mode_group.addButton(btn, i)
            self.mode_buttons[kind] = btn
            lay.addWidget(btn)
        self.mode_buttons[GroupKind.SCENE].setChecked(True)
        self.mode_group.idToggled.connect(self._on_mode_changed)

        lay.addSpacing(8)
        lay.addWidget(section_title("Benzerlik eşiği"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        # Tutamaç oluktan taşar; yükseklik verilmezse altı üstü kesik görünür
        self.threshold_slider.setMinimumHeight(30)
        self.threshold_slider.setRange(50, 100)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        lay.addWidget(self.threshold_slider)
        scale = QHBoxLayout()
        left, right = QLabel("Esnek"), QLabel("Katı")
        left.setObjectName("muted")
        right.setObjectName("muted")
        self.threshold_label = QLabel()
        self.threshold_label.setStyleSheet("font-weight: 600;")
        scale.addWidget(left)
        scale.addStretch(1)
        scale.addWidget(self.threshold_label)
        scale.addStretch(1)
        scale.addWidget(right)
        lay.addLayout(scale)

        self.window_title = section_title("Zaman penceresi")
        lay.addWidget(self.window_title)
        wrow = QHBoxLayout()
        self.window_combo = QComboBox()
        for sec in WINDOW_CHOICES:
            self.window_combo.addItem(window_text(sec), sec)
        self.window_combo.setCurrentIndex(WINDOW_CHOICES.index(self.app_settings.scene_window))
        self.window_combo.currentIndexChanged.connect(lambda _: self._regroup_timer.start())
        wrow.addWidget(self.window_combo)
        self.window_hint = QLabel("EXIF çekim zamanına göre")
        self.window_hint.setObjectName("muted")
        wrow.addWidget(self.window_hint, 1)
        lay.addLayout(wrow)

        lay.addSpacing(8)
        lay.addWidget(section_title("Formatlar"))
        frow = QHBoxLayout()
        self.format_boxes: dict[str, QCheckBox] = {}
        for name, _ in FORMATS:
            box = QCheckBox(name)
            box.setChecked(True)
            self.format_boxes[name] = box
            frow.addWidget(box)
        frow.addStretch(1)
        lay.addLayout(frow)

        lay.addStretch(1)
        self.progress_label = QLabel("Henüz tarama yapılmadı")
        self.progress_label.setObjectName("muted")
        self.progress_label.setWordWrap(True)
        lay.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setValue(0)
        lay.addWidget(self.progress_bar)
        self.scan_button = QPushButton("🔍  TARA")
        self.scan_button.setObjectName("scanButton")
        self.scan_button.clicked.connect(self._on_scan_clicked)
        lay.addWidget(self.scan_button)
        return panel

    # ------------------------------------------------------------------
    # Orta panel
    # ------------------------------------------------------------------

    def _build_mid_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("midPanel")
        panel.setFixedWidth(370)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(14, 14, 14, 10)
        hl.setSpacing(8)
        self.groups_title = section_title("Bulunan gruplar")
        hl.addWidget(self.groups_title)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_all = QPushButton("Tümü")
        self.chip_open = QPushButton("İncelenmemiş")
        self.chip_reviewed = QPushButton("İncelendi")
        self.chip_marked = QPushButton("İşaretli")
        self.chip_open.setToolTip("Henüz incelenmemiş gruplar")
        self.chip_reviewed.setToolTip(
            "İncelenmiş gruplar: seçimini değiştirdiğiniz ya da Sonraki/Page Down ile geçtiğiniz gruplar"
        )
        self.chip_marked.setToolTip("En az bir fotoğrafı işaretli gruplar")
        self.chip_group = QButtonGroup(self)
        for chip in (self.chip_all, self.chip_open, self.chip_reviewed, self.chip_marked):
            chip.setObjectName("chip")
            chip.setCheckable(True)
            self.chip_group.addButton(chip)
            chips.addWidget(chip)
        self.chip_all.setChecked(True)
        self.chip_group.buttonToggled.connect(lambda *_: self._apply_filter())
        chips.addStretch(1)
        hl.addLayout(chips)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_CHOICES)
        self.sort_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        hl.addWidget(self.sort_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔎 Klasör veya dosya adında ara…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _: self._apply_filter())
        hl.addWidget(self.search_edit)
        lay.addWidget(head)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #eeeeee;")
        lay.addWidget(line)

        self.group_model = GroupListModel(self)
        self.group_delegate = GroupDelegate(self.thumbs, self)
        self.group_view = QListView()
        self.group_view.setObjectName("groupList")
        self.group_view.setModel(self.group_model)
        self.group_view.setItemDelegate(self.group_delegate)
        self.group_view.setUniformItemSizes(True)
        self.group_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.group_view.selectionModel().currentChanged.connect(self._on_group_selected)
        self.group_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.group_view.customContextMenuRequested.connect(self._group_menu)
        self.thumbs.loaded.connect(lambda _p: self.group_view.viewport().update())
        lay.addWidget(self.group_view, 1)

        self.empty_label = QLabel()
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(self.empty_label)
        return panel

    # ------------------------------------------------------------------
    # Sağ panel
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("rightPanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QFrame()
        header.setObjectName("rightHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 10)
        hl.setSpacing(10)
        self.kind_tag = QLabel()
        self.kind_tag.setObjectName("kindTag")
        hl.addWidget(self.kind_tag)
        self.group_label = QLabel()
        self.group_label.setObjectName("groupTitle")
        hl.addWidget(self.group_label)
        self.group_time = QLabel()
        self.group_time.setObjectName("muted")
        hl.addWidget(self.group_time)
        hl.addStretch(1)
        self.prev_button = QPushButton("◀ Önceki")
        self.prev_button.setToolTip("Önceki grup (Page Up)")
        self.prev_button.clicked.connect(lambda: self._step_group(-1))
        self.next_button = QPushButton("Sonraki ▶")
        self.next_button.setToolTip("Sonraki grup (Page Down)")
        self.next_button.clicked.connect(lambda: self._step_group(1))
        self.reset_button = QPushButton("Önerileni seç")
        self.reset_button.setToolTip("★ dışındakileri işaretle (varsayılan)")
        self.reset_button.clicked.connect(self._reset_marks)
        self.clear_button = QPushButton("Seçimi temizle")
        self.clear_button.setToolTip("Bu gruptaki hiçbir dosyayı ayırma")
        self.clear_button.clicked.connect(self._clear_marks)
        self.reviewed_button = QPushButton("✓ İncelendi")
        self.reviewed_button.setObjectName("reviewedToggle")
        self.reviewed_button.setCheckable(True)
        self.reviewed_button.setToolTip(
            "Grubu incelendi olarak işaretle ya da işareti kaldır.\n"
            "Seçimi değiştirince ya da Sonraki/Page Down ile geçince kendiliğinden işaretlenir."
        )
        self.reviewed_button.toggled.connect(self._on_reviewed_toggled)
        self.more_button = QToolButton()
        self.more_button.setText("⋯")
        self.more_button.setToolTip("Diğer grup işlemleri")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self.more_button)
        self.discard_group_action = more_menu.addAction(
            "🗑 Grubun tamamını Geri Dönüşüm Kutusu'na gönder…", self._discard_current_group
        )
        self.more_button.setMenu(more_menu)
        for b in (self.prev_button, self.next_button, self.reset_button, self.clear_button, self.reviewed_button, self.more_button):
            hl.addWidget(b)
        lay.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.grid = ThumbnailGrid(self.thumbs)
        self.grid.card_clicked.connect(self._focus_item)
        self.grid.mark_toggled.connect(self._on_mark_toggled)
        self.grid.keep_requested.connect(self._keep_only)
        self.grid.open_folder_requested.connect(self._open_in_explorer)
        self.grid.discard_group_requested.connect(self._discard_current_group)
        splitter.addWidget(self.grid)

        preview_wrap = QWidget()
        pw = QVBoxLayout(preview_wrap)
        pw.setContentsMargins(16, 0, 16, 14)
        frame = QFrame()
        frame.setObjectName("previewFrame")
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.setSpacing(0)
        self.preview = ImagePreview()
        fl.addWidget(self.preview, 1)
        self.details = DetailsPanel()
        fl.addWidget(self.details)
        pw.addWidget(frame)
        splitter.addWidget(preview_wrap)
        splitter.setSizes([440, 380])
        splitter.setChildrenCollapsible(False)
        lay.addWidget(splitter, 1)
        return panel

    # ------------------------------------------------------------------
    # Alt çubuk ve durum çubuğu
    # ------------------------------------------------------------------

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(10)
        self.summary_label = QLabel()
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        f = QFont(self.summary_label.font())
        f.setPointSizeF(f.pointSizeF() + 1)
        self.summary_label.setFont(f)
        lay.addWidget(self.summary_label)
        lay.addStretch(1)
        self.history_button = QPushButton("🕘 Geçmiş")
        self.history_button.setToolTip("Yapılan taşıma ve geri dönüşüm işlemleri; istenen işlem geri alınabilir")
        self.history_button.clicked.connect(self._show_history)
        self.undo_button = QPushButton("↶ Geri Al")
        self.undo_button.clicked.connect(self._undo_last)
        self.settings_button = QPushButton("⚙ Ayarlar")
        self.settings_button.setToolTip("Varsayılan eşikler, zaman penceresi ve tarama işçi sayısı")
        self.settings_button.clicked.connect(self._show_settings)
        self.report_button = QPushButton("📄 Rapor")
        self.report_button.setToolTip("Seçili moddaki grupları HTML (küçük resimli) ya da CSV (Excel) olarak kaydeder")
        self.report_button.clicked.connect(self._export_report)
        self.trash_button = QPushButton("🗑 Geri Dönüşüm Kutusu'na gönder")
        self.trash_button.setToolTip("İşaretli dosyaları Geri Dönüşüm Kutusu'na gönderir (geri alınabilir)")
        self.trash_button.clicked.connect(lambda: self._run_action(KIND_TRASH))
        self.move_button = QPushButton(f"📦 {DUPLICATES_FOLDER_NAME} klasörüne taşı")
        self.move_button.setObjectName("primary")
        self.move_button.setToolTip(
            f"İşaretli dosyaları tarama klasörünün içindeki {DUPLICATES_FOLDER_NAME} klasörüne, "
            "alt klasör yapısını koruyarak taşır (geri alınabilir)"
        )
        self.move_button.clicked.connect(lambda: self._run_action(KIND_MOVE))
        for b in (self.settings_button, self.history_button, self.undo_button, self.report_button, self.trash_button, self.move_button):
            lay.addWidget(b)
        return bar

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        self.cache_status = QLabel()
        self.rule_status = QLabel()
        sb.addWidget(self.cache_status)
        sb.addWidget(QLabel("   "))
        sb.addWidget(self.rule_status)
        self.help_button = QPushButton("⌨ Kısayollar (F1)")
        self.help_button.setObjectName("statusLink")
        self.help_button.setFlat(True)
        self.help_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_button.setToolTip("Klavye kısayollarını göster")
        self.help_button.clicked.connect(self._show_shortcuts)
        sb.addPermanentWidget(self.help_button)
        sb.addPermanentWidget(QLabel(f"Kalıcı silme yapılmaz · BenzerFoto {__version__}  "))

    def _build_shortcuts(self) -> None:
        """Klavye kısayolları: hangi panel odakta olursa olsun çalışır.

        QShortcut yerine uygulama düzeyinde olay süzgeci kullanılır; böylece grup
        listesi ya da kaydırıcı gibi okları kendisi kullanan bileşenler kısayolu
        yutmaz. Metin kutusuna yazılırken kısayollar devre dışıdır.
        Tablo: tuş → (düz basış, Ctrl ile, basılı tutunca tekrarlansın mı).
        """
        Key = Qt.Key
        self._key_actions = {
            Key.Key_PageDown: (lambda: self._step_group(1), None, True),
            Key.Key_PageUp: (lambda: self._step_group(-1), None, True),
            Key.Key_Right: (lambda: self._step_photo(1), lambda: self._step_group(1), True),
            Key.Key_Left: (lambda: self._step_photo(-1), lambda: self._step_group(-1), True),
            Key.Key_Space: (self._toggle_focused_mark, None, False),
            Key.Key_Delete: (self._trash_focused, None, False),
            Key.Key_F1: (self._show_shortcuts, None, False),
        }
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt adı)
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(obj, QWidget)
            and obj.window() is self
            and self._handle_key(event)
        ):
            return True
        return super().eventFilter(obj, event)

    def _handle_key(self, event) -> bool:
        entry = self._key_actions.get(event.key())
        if entry is None:
            return False
        # Pencerenin kendi odak bileşeni: pencere etkin değilken de doğru sonuç verir
        focus = self.focusWidget()
        if event.key() != Qt.Key.Key_F1 and isinstance(focus, TEXT_INPUTS) and not getattr(focus, "isReadOnly", lambda: False)():
            return False
        plain, with_ctrl, repeat_ok = entry
        mods = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        if mods == Qt.KeyboardModifier.NoModifier:
            action = plain
        elif mods == Qt.KeyboardModifier.ControlModifier:
            action = with_ctrl
        else:
            action = None
        if action is None:
            return False
        if event.isAutoRepeat() and not repeat_ok:
            return True  # basılı tutulan Boşluk/Delete tekrar tekrar işlem yapmasın
        action()
        return True

    # ------------------------------------------------------------------
    # Klasör yönetimi
    # ------------------------------------------------------------------

    def _folders(self, kind: str) -> list[str]:
        return [
            self.folder_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.folder_list.count())
            if self.folder_list.item(i).data(ROLE_KIND) == kind
        ]

    def _append_folder(self, path: str, kind: str) -> None:
        path = os.path.normpath(path)
        for i in range(self.folder_list.count()):
            it = self.folder_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == path and it.data(ROLE_KIND) == kind:
                return
        item = QListWidgetItem(f"{FOLDER_ICONS[kind]}  {path}")
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(ROLE_KIND, kind)
        item.setToolTip({FOLDER_SCAN: "Taranır", FOLDER_EXCLUDE: "Hariç tutulur", FOLDER_PROTECT: "Korunur: buradaki fotoğraflar asla işaretlenmez"}[kind])
        if kind == FOLDER_EXCLUDE:
            font = item.font()
            font.setStrikeOut(True)
            item.setFont(font)
            item.setForeground(Qt.GlobalColor.darkRed)
        elif kind == FOLDER_PROTECT:
            item.setForeground(Qt.GlobalColor.darkGreen)
        self.folder_list.addItem(item)

    def _add_folder(self, kind: str) -> None:
        start = (self._folders(FOLDER_SCAN) or [str(Path.home())])[0]
        title = {FOLDER_SCAN: "Taranacak klasörü seç", FOLDER_EXCLUDE: "Hariç tutulacak klasörü seç", FOLDER_PROTECT: "Korunacak klasörü seç"}[kind]
        path = QFileDialog.getExistingDirectory(self, title, start)
        if path:
            self._append_folder(path, kind)
            self._save_settings()
            if kind == FOLDER_PROTECT:
                self._reapply_protection()

    def _remove_folder(self) -> None:
        row = self.folder_list.currentRow()
        if row >= 0:
            kind = self.folder_list.item(row).data(ROLE_KIND)
            self.folder_list.takeItem(row)
            self._save_settings()
            if kind == FOLDER_PROTECT:
                self._reapply_protection()

    # ------------------------------------------------------------------
    # Tarama
    # ------------------------------------------------------------------

    def _selected_extensions(self) -> list[str]:
        return [ext for name, exts in FORMATS if self.format_boxes[name].isChecked() for ext in exts]

    def _on_scan_clicked(self) -> None:
        if self.scan_thread is not None:
            self.scan_thread.cancel()
            self.scan_button.setEnabled(False)
            self.progress_label.setText("Durduruluyor, çalışan işler bitiriliyor…")
            return
        if self._busy:
            return
        roots = self._folders(FOLDER_SCAN)
        if not roots:
            QMessageBox.information(self, "BenzerFoto", "Önce taranacak en az bir klasör ekleyin (+ Ekle).")
            return
        missing = [r for r in roots if not os.path.isdir(r)]
        if missing:
            QMessageBox.warning(self, "BenzerFoto", "Bu klasörler bulunamadı:\n" + "\n".join(missing))
            return
        if not self._selected_extensions():
            QMessageBox.information(self, "BenzerFoto", "En az bir format seçin.")
            return
        self._save_settings()
        self.scan_thread = ScanThread(
            self.db_path,
            roots,
            self._folders(FOLDER_EXCLUDE),
            self.recursive_box.isChecked(),
            self._selected_extensions(),
            self.app_settings.effective_workers(),
            self,
        )
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.succeeded.connect(self._on_scan_finished)
        self.scan_thread.failed.connect(self._on_scan_failed)
        self.scan_thread.finished.connect(self._on_scan_thread_done)
        self.scan_button.setText("⏹  DURDUR")
        self.scan_button.setProperty("running", True)
        self._repolish(self.scan_button)
        self.progress_bar.setRange(0, 0)  # belirsiz: dosyalar aranıyor
        self.progress_label.setText("Dosyalar aranıyor…")
        self.scan_thread.start()
        self._update_action_buttons()

    def _on_scan_progress(self, phase: str, done: int, total: int) -> None:
        if phase == "discover":
            self.progress_label.setText(f"Dosyalar aranıyor… {format_count(done)} bulundu")
        elif phase == "process":
            if total == 0:
                self.progress_label.setText("Tüm dosyalar önbellekte, gruplar hazırlanıyor…")
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(1)
            else:
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(done)
                self.progress_label.setText(f"İşleniyor: {format_count(done)} / {format_count(total)} (%{100 * done // total})")

    def _on_scan_finished(self, result) -> None:
        self.features = result.features
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        text = (
            f"{'Tarama durduruldu' if result.cancelled else 'Tarama tamamlandı'} · {format_count(result.total_files)} dosya\n"
            f"Önbellekten: {format_count(result.from_cache)} · Yeni: {format_count(result.processed)}"
        )
        if result.failed:
            text += f" · Okunamayan: {result.failed}"
        text += f" · {self._format_duration(result.elapsed)}"
        self.progress_label.setText(text)
        self._update_cache_status()
        self._regroup_all()

    def _on_scan_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Tarama hata verdi")
        QMessageBox.critical(self, "Tarama hatası", message)

    def _on_scan_thread_done(self) -> None:
        self.scan_thread = None
        self.scan_button.setEnabled(True)
        self.scan_button.setText("🔍  TARA")
        self.scan_button.setProperty("running", False)
        self._repolish(self.scan_button)
        self._update_action_buttons()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f} sn"
        return f"{int(seconds // 60)} dk {int(seconds % 60)} sn"

    # ------------------------------------------------------------------
    # Gruplama
    # ------------------------------------------------------------------

    def current_kind(self) -> GroupKind:
        return [GroupKind.EXACT, GroupKind.SIMILAR, GroupKind.SCENE][self.mode_group.checkedId()]

    def _group_params(self, kind: GroupKind) -> dict:
        params: dict = {"protected_folders": self._folders(FOLDER_PROTECT)}
        if kind in self.thresholds:
            params["max_distance"] = similarity_to_distance(self.thresholds[kind])
        if kind == GroupKind.SCENE:
            params["window_seconds"] = self.window_combo.currentData()
        return params

    def _regroup_all(self) -> None:
        """Tarama sonrası üç modu birden hesaplar (sayılar mod düğmelerinde görünür)."""
        self._group_request += 1
        request = self._group_request
        features = list(self.features)
        params = {k: self._group_params(k) for k in GroupKind}
        self.groups_title.setText("BULUNAN GRUPLAR · HESAPLANIYOR…")

        db_path = self.db_path

        def work():
            groups = {k: build_groups(features, k, **params[k]) for k in GroupKind}
            review.load_and_apply(db_path, groups)  # dünkü kararlar geri gelsin
            return groups

        run_async(work, lambda res: self._on_groups_ready(request, res))

    def _regroup_current(self) -> None:
        """Eşik ya da zaman penceresi değişince yalnızca seçili modu yeniden hesaplar."""
        if not self.features:
            return
        self._group_request += 1
        request = self._group_request
        kind = self.current_kind()
        features = list(self.features)
        params = self._group_params(kind)
        db_path = self.db_path
        self.groups_title.setText("BULUNAN GRUPLAR · HESAPLANIYOR…")

        def work():
            groups = {kind: build_groups(features, kind, **params)}
            review.load_and_apply(db_path, groups)
            return groups

        run_async(work, lambda res: self._on_groups_ready(request, res))

    def _on_groups_ready(self, request: int, result: dict) -> None:
        if request != self._group_request:
            return  # bu arada yeni bir hesaplama başlatılmış
        self.groups_by_kind.update(result)
        self._update_mode_labels()
        self._apply_filter()
        self._update_summary()

    def _reapply_protection(self) -> None:
        """Koruma klasörleri değişince mevcut grupları yeniden değerlendirir."""
        protected = self._folders(FOLDER_PROTECT)
        for groups in self.groups_by_kind.values():
            for g in groups:
                choose_best(g, protected)
        self._update_rule_status()
        self._refresh_current_group()

    def _update_mode_labels(self) -> None:
        names = {GroupKind.EXACT: "Birebir kopya", GroupKind.SIMILAR: "Benzer görüntü", GroupKind.SCENE: "Aynı sahne"}
        for kind, btn in self.mode_buttons.items():
            n = len(self.groups_by_kind[kind])
            btn.setText(f"{names[kind]}  ({format_count(n)})" if self.features else names[kind])

    def _on_mode_changed(self, _id: int, checked: bool) -> None:
        if not checked:
            return
        self._update_mode_controls()
        self._apply_filter()
        self._update_summary()
        self._save_settings()

    def _update_mode_controls(self) -> None:
        kind = self.current_kind()
        has_threshold = kind in self.thresholds
        self.threshold_slider.setEnabled(has_threshold)
        self.threshold_slider.blockSignals(True)
        self.threshold_slider.setValue(round(self.thresholds.get(kind, 100)))
        self.threshold_slider.blockSignals(False)
        self.threshold_label.setText(f"%{self.threshold_slider.value()}" if has_threshold else "içerik aynı")
        for w in (self.window_title, self.window_combo, self.window_hint):
            w.setVisible(kind == GroupKind.SCENE)

    def _on_threshold_changed(self, value: int) -> None:
        kind = self.current_kind()
        if kind not in self.thresholds:
            return
        self.thresholds[kind] = float(value)
        bits = similarity_to_distance(value)
        self.threshold_label.setText(f"%{value}")
        self.threshold_slider.setToolTip(f"En fazla {bits} bit fark")
        self._regroup_timer.start()

    # ------------------------------------------------------------------
    # Grup listesi, filtre, gezinme
    # ------------------------------------------------------------------

    def _apply_filter(self, keep_row: bool = False) -> None:
        """Grup listesini filtreler ve sıralar.

        keep_row: seçili grup listeden düşerse (ör. dosyaları gönderildi) başa
        dönmek yerine aynı sıradaki gruba geçilir.
        """
        old_row = self.group_view.currentIndex().row()
        groups = list(self.groups_by_kind[self.current_kind()])
        query = self.search_edit.text().strip().lower()
        if query:
            groups = [g for g in groups if any(query in m.path.lower() for m in g.members)]
        if self.chip_open.isChecked():
            groups = [g for g in groups if not g.reviewed]
        elif self.chip_reviewed.isChecked():
            groups = [g for g in groups if g.reviewed]
        elif self.chip_marked.isChecked():
            groups = [g for g in groups if g.marked]

        self._sort_groups(groups)
        previous = self.current_group
        self.visible_groups = groups
        self.group_model.set_groups(groups)
        total = len(self.groups_by_kind[self.current_kind()])
        shown = f"{format_count(len(groups))} / {format_count(total)}" if len(groups) != total else format_count(total)
        self.groups_title.setText(f"BULUNAN GRUPLAR · {shown}")
        self._update_review_counts()

        if not self.features:
            self.empty_label.setText("Klasör ekleyip TARA'ya basın.\nİlk tarama uzun sürebilir; sonrakiler önbellekten hızlı gelir.")
        elif not groups:
            self.empty_label.setText("Bu ayarlarla grup bulunamadı.\nEşiği esnetmeyi ya da başka bir modu deneyin.")
        self.empty_label.setVisible(not groups)

        if groups:
            if previous in groups:
                row = groups.index(previous)
            else:
                row = min(max(old_row, 0), len(groups) - 1) if keep_row else 0
            self.group_view.setCurrentIndex(self.group_model.index(row))
        else:
            self._show_group(None)

    def _sort_groups(self, groups: list[PhotoGroup]) -> None:
        sort = self.sort_combo.currentIndex()
        if sort == 0:
            groups.sort(key=lambda g: -g.marked_size)
        elif sort == 1:
            groups.sort(key=lambda g: (-len(g.members), -g.total_size))
        else:
            groups.sort(key=lambda g: max((m.taken_at or "") for m in g.members), reverse=True)

    def _on_group_selected(self, current, _previous) -> None:
        group = self.group_model.data(current, GroupListModel.GroupRole) if current.isValid() else None
        self._show_group(group)

    def _step_group(self, delta: int) -> None:
        if not self.visible_groups:
            return
        if delta > 0 and self.current_group is not None:
            self._mark_reviewed(self.current_group)  # sonrakine geçilen grup incelenmiş sayılır
        row = self.group_view.currentIndex().row() + delta
        row = max(0, min(len(self.visible_groups) - 1, row))
        self.group_view.setCurrentIndex(self.group_model.index(row))

    def _show_group(self, group: PhotoGroup | None) -> None:
        self.current_group = group
        has = group is not None
        for b in (self.prev_button, self.next_button, self.reset_button, self.clear_button, self.reviewed_button, self.more_button):
            b.setEnabled(has)
        self._sync_reviewed_button()
        if not has:
            self.kind_tag.hide()
            self.group_label.setText("Grup seçilmedi")
            self.group_time.setText("")
            self.grid.show_group(None, None)
            self.preview.set_pixmap(None, message="Önizleme için bir grup seçin")
            self.details.show_item(None, None)
            self._update_summary()
            return
        bg, fg = TAG_COLORS[group.kind.value]
        self.kind_tag.setText(group.kind.label.upper())
        self.kind_tag.setStyleSheet(f"background: {bg}; color: {fg};")
        self.kind_tag.show()
        row = self.visible_groups.index(group) + 1 if group in self.visible_groups else 0
        self.group_label.setText(f"Grup #{row} · {len(group.members)} fotoğraf · {format_size(group.total_size)}")
        self.group_time.setText(scene_time_range(group))
        # Aynı grup yeniden gösteriliyorsa (filtre, silme) odaktaki fotoğraf korunur
        same = group is self._shown_group and self.focused_path in {m.path for m in group.members}
        if not same:
            self.focused_path = group.best_path or group.members[0].path
        self._shown_group = group
        self.grid.show_group(group, self.focused_path)
        self._show_preview(self.focused_path)
        self._update_summary()

    def _refresh_current_group(self) -> None:
        group = self.current_group
        if group is None:
            return
        self._sync_reviewed_button()
        self.grid.update_states(group, self.focused_path)
        self.details.show_item(self._item(self.focused_path), group)
        row = self.group_view.currentIndex().row()
        if row >= 0:
            self.group_model.refresh_row(row)
        self._update_summary()

    def _item(self, path: str | None) -> ImageFeatures | None:
        if self.current_group is None:
            return None
        return next((m for m in self.current_group.members if m.path == path), None)

    # ------------------------------------------------------------------
    # Önizleme ve işaretleme
    # ------------------------------------------------------------------

    def _focus_item(self, path: str) -> None:
        self.focused_path = path
        if self.current_group:
            self.grid.update_states(self.current_group, path)
        self._show_preview(path)

    def _show_preview(self, path: str | None) -> None:
        item = self._item(path)
        self.details.show_item(item, self.current_group)
        if item is None:
            self.preview.set_pixmap(None)
            return
        # Önce küçük resmi hemen göster, büyük hali arka planda yükle
        thumb = self.thumbs.get(item.path)
        self.preview.set_pixmap(thumb, item.width or 0, "" if thumb else "Yükleniyor…")
        self._preview_request += 1
        request = self._preview_request

        def done(image) -> None:
            if request != self._preview_request:
                return
            if image is None or image.isNull():
                self.preview.set_pixmap(None, message="Bu dosya önizlenemiyor")
            else:
                self.preview.set_pixmap(QPixmap.fromImage(image), item.width or image.width())

        run_async(lambda: load_qimage(item.path, 4096), done, lambda _msg: done(None))

    def _on_mark_toggled(self, path: str, on: bool) -> None:
        group = self.current_group
        if group is None or path in group.protected:
            return
        if on:
            group.marked.add(path)
        else:
            group.marked.discard(path)
        if on and len(group.marked) == len(group.members):
            QMessageBox.warning(self, "BenzerFoto", "Gruptaki tüm fotoğrafları işaretlediniz. En az birini tutmanız önerilir.")
        self._mark_reviewed(group)
        self._refresh_current_group()

    def _step_photo(self, delta: int) -> None:
        """Seçili grubun içinde odaktaki fotoğrafı değiştirir (← / →)."""
        group = self.current_group
        if group is None or not group.members:
            return
        paths = [m.path for m in group.members]  # ızgaradaki sırayla aynı
        if self.focused_path in paths:
            index = max(0, min(len(paths) - 1, paths.index(self.focused_path) + delta))
        else:
            index = 0
        self._focus_item(paths[index])
        self.grid.ensure_visible(paths[index])

    def _toggle_focused_mark(self) -> None:
        if self.current_group and self.focused_path:
            self._on_mark_toggled(self.focused_path, self.focused_path not in self.current_group.marked)

    def _keep_only(self, path: str) -> None:
        """Seçilen fotoğrafı ★ yapar, korunmayan diğerlerini işaretler."""
        group = self.current_group
        if group is None:
            return
        group.best_path = path
        group.marked = {m.path for m in group.members if m.path != path and m.path not in group.protected}
        self._mark_reviewed(group)
        self._refresh_current_group()

    def _reset_marks(self) -> None:
        if self.current_group:
            choose_best(self.current_group, self._folders(FOLDER_PROTECT))
            self._mark_reviewed(self.current_group)
            self._refresh_current_group()

    def _clear_marks(self) -> None:
        if self.current_group:
            self.current_group.marked.clear()
            self._mark_reviewed(self.current_group)
            self._refresh_current_group()

    def _trash_focused(self) -> None:
        """Delete: yalnızca odaktaki fotoğrafı onay sorarak Geri Dönüşüm Kutusu'na gönderir."""
        group, path = self.current_group, self.focused_path
        if not self._is_idle() or group is None or path is None:
            return
        item = self._item(path)
        if item is None:
            return
        name = os.path.basename(path)
        if path in group.protected:
            QMessageBox.information(self, "BenzerFoto", f"{name} korunan bir klasörde; gönderilemez.")
            return
        if not recycle.is_trash_supported(path):
            QMessageBox.warning(
                self,
                "BenzerFoto",
                f"{name} Geri Dönüşüm Kutusu olmayan bir sürücüde (ağ ya da USB). Windows kalıcı "
                f"sileceği için gönderilmedi. “{DUPLICATES_FOLDER_NAME} klasörüne taşı” seçeneğini kullanın.",
            )
            return
        answer = QMessageBox.question(
            self,
            "BenzerFoto",
            f"Bu fotoğraf Geri Dönüşüm Kutusu'na gönderilsin mi?\n\n{name} · {format_size(item.size)}\n"
            f"{os.path.dirname(path)}\n\nGeri Al ile geri getirilebilir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        index = [m.path for m in group.members].index(path)
        db_path = self.db_path
        self._start_job(
            "Geri Dönüşüm Kutusu'na gönderiliyor…",
            lambda progress: actions.send_to_trash(db_path, [path], progress),
            lambda result: self._on_single_trash_done(result, group, index),
        )

    def _on_single_trash_done(self, result: actions.ActionResult, group: PhotoGroup, index: int) -> None:
        """Tek dosya gönderildi: bilgi penceresi açmadan durum çubuğunda haber verir."""
        self._apply_removal(set(result.done))
        self._refresh_undo_state()
        if result.failed:
            QMessageBox.warning(self, "BenzerFoto", self._failure_text(result.failed))
            return
        if self.current_group is group and group.members:
            path = group.members[min(index, len(group.members) - 1)].path
            self._focus_item(path)
            self.grid.ensure_visible(path)
        self.statusBar().showMessage(
            f"{format_count(len(result.done))} dosya Geri Dönüşüm Kutusu'na gönderildi. Geri Al ile geri alabilirsiniz.",
            15000,
        )

    # ------------------------------------------------------------------
    # İnceleme durumu
    # ------------------------------------------------------------------

    def _save_review(self, group: PhotoGroup) -> None:
        try:
            with review.ReviewStore(self.db_path) as store:
                store.save_group(group)
        except Exception as exc:  # kayıt yazılamazsa çalışma sürer, kullanıcı uyarılır
            self.statusBar().showMessage(f"İnceleme durumu kaydedilemedi: {exc}", 15000)

    def _mark_reviewed(self, group: PhotoGroup) -> None:
        """Grubu incelendi yapar; işaretleri de kaydeder (yarın kaldığı yerden devam)."""
        group.reviewed = True
        self._save_review(group)
        self._after_review_change(group)

    def _on_reviewed_toggled(self, on: bool) -> None:
        group = self.current_group
        if group is None or group.reviewed == on:
            return
        group.reviewed = on
        self._save_review(group)
        self._after_review_change(group)

    def _after_review_change(self, group: PhotoGroup) -> None:
        if group is self.current_group:
            self._sync_reviewed_button()
        if group in self.visible_groups:
            self.group_model.refresh_row(self.visible_groups.index(group))
        self._update_review_counts()

    def _sync_reviewed_button(self) -> None:
        group = self.current_group
        self.reviewed_button.blockSignals(True)
        self.reviewed_button.setChecked(bool(group and group.reviewed))
        self.reviewed_button.blockSignals(False)

    def reviewed_groups(self) -> list[PhotoGroup]:
        return [g for g in self.groups_by_kind[self.current_kind()] if g.reviewed]

    def _update_review_counts(self) -> None:
        groups = self.groups_by_kind[self.current_kind()]
        done = sum(1 for g in groups if g.reviewed)
        self.chip_open.setText(f"İncelenmemiş ({format_count(len(groups) - done)})" if groups else "İncelenmemiş")
        self.chip_reviewed.setText(f"İncelendi ({format_count(done)})" if groups else "İncelendi")

    def _group_menu(self, pos) -> None:
        index = self.group_view.indexAt(pos)
        if not index.isValid():
            return
        self.group_view.setCurrentIndex(index)
        menu = QMenu(self)
        reviewed = bool(self.current_group and self.current_group.reviewed)
        menu.addAction("İncelendi işaretini kaldır" if reviewed else "✓ İncelendi olarak işaretle", self.reviewed_button.toggle)
        menu.addSeparator()
        menu.addAction("🗑 Grubun tamamını Geri Dönüşüm Kutusu'na gönder…", self._discard_current_group)
        menu.exec(self.group_view.viewport().mapToGlobal(pos))

    def _confirm_discard(self, group: PhotoGroup, paths: list[str], size: int) -> bool:
        """Grubun tamamını göndermek için iki aşamalı onay."""
        first = QMessageBox.warning(
            self,
            "Grubun tamamı",
            f"Bu gruptaki {len(paths)} fotoğrafın HİÇBİRİ tutulmayacak; hepsi Geri Dönüşüm "
            f"Kutusu'na gönderilecek ({format_size(size)}).\n\n"
            "Normalde her gruptan en az bir fotoğraf kalır. Bu işlem bu kuralı yalnızca bu grup "
            "için kaldırır. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return False
        dialog = DiscardGroupDialog(len(paths), format_size(size), self)
        return dialog.exec() == DiscardGroupDialog.DialogCode.Accepted

    def _discard_current_group(self) -> None:
        """Grubun korunmayan tüm fotoğraflarını Geri Dönüşüm Kutusu'na gönderir (geri alınabilir)."""
        group = self.current_group
        if group is None or not self._is_idle():
            return
        members = [m for m in group.members if m.path not in group.protected]
        if not members:
            QMessageBox.information(self, "BenzerFoto", "Bu gruptaki tüm fotoğraflar korunan klasörde; gönderilecek dosya yok.")
            return
        paths = [m.path for m in members]
        size = sum(m.size for m in members)
        unsupported = [p for p in paths if not recycle.is_trash_supported(p)]
        if unsupported:
            QMessageBox.warning(
                self,
                "BenzerFoto",
                f"{len(unsupported)} dosya Geri Dönüşüm Kutusu olmayan bir sürücüde (ağ ya da USB). "
                "Windows bu dosyaları kalıcı sileceği için işlem yapılmadı.",
            )
            return
        if not self._confirm_discard(group, paths, size):
            return
        if len(members) < len(group.members):
            self.statusBar().showMessage(f"{len(group.members) - len(members)} korunan fotoğraf gruba bırakıldı.", 15000)
        db_path = self.db_path
        self._start_job(
            "Grubun tamamı Geri Dönüşüm Kutusu'na gönderiliyor…",
            lambda progress: actions.send_to_trash(db_path, paths, progress),
            lambda result: self._on_action_done(KIND_TRASH, result),
        )

    def _open_in_explorer(self, path: str) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    # ------------------------------------------------------------------
    # Dosya işlemleri: taşıma, geri dönüşüm, geri alma (4. aşama)
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_marked(groups: list[PhotoGroup]) -> tuple[list[str], int, int]:
        """İşlenecek yollar, toplam boyut ve atlanan grup sayısı.

        Tüm üyeleri işaretli gruplar atlanır: her gruptan en az bir fotoğraf kalır.
        Korunan dosyalar hiçbir durumda işleme girmez.
        """
        paths: list[str] = []
        size = 0
        skipped = 0
        for g in groups:
            marked = g.marked - g.protected
            if not marked:
                continue
            if len(marked) >= len(g.members):
                skipped += 1
                continue
            for m in g.members:
                if m.path in marked:
                    paths.append(m.path)
                    size += m.size
        return paths, size, skipped

    def _ask_scope(self, kind: str) -> list[PhotoGroup] | None:
        """İşlemin kapsamını sorar: tüm gruplar, incelenen gruplar ya da yalnızca seçili grup."""
        all_groups = self.groups_by_kind[self.current_kind()]
        all_paths, all_size, skipped = self._collect_marked(all_groups)
        here_paths, here_size, _ = self._collect_marked([self.current_group] if self.current_group else [])
        reviewed = self.reviewed_groups()
        rev_paths, rev_size, _ = self._collect_marked(reviewed)

        box = QMessageBox(self)
        box.setWindowTitle("BenzerFoto")
        box.setIcon(QMessageBox.Icon.Question)
        if kind == KIND_MOVE:
            box.setText("İşaretli dosyalar <b>_benzerler</b> klasörüne taşınsın mı?")
            info = (
                f"Her dosya, bulunduğu tarama klasörünün içindeki {DUPLICATES_FOLDER_NAME} klasörüne "
                "alt klasör yapısı korunarak taşınır. Hiçbir dosya silinmez; Geri Al ile geri getirilebilir."
            )
        else:
            box.setText("İşaretli dosyalar <b>Geri Dönüşüm Kutusu</b>'na gönderilsin mi?")
            info = (
                "Kutu boşaltılmadığı sürece Geri Al ile geri getirilebilir. "
                "Kutuya sığmayacak kadar büyük bir dosya olursa Windows ayrıca sorar."
            )
        if skipped:
            info += f"\n\nTüm fotoğrafları işaretli {skipped} grup atlanacak (her gruptan en az biri kalır)."
        box.setInformativeText(info)
        all_btn = box.addButton(
            f"Tüm gruplar ({format_count(len(all_paths))} dosya · {format_size(all_size)})",
            QMessageBox.ButtonRole.AcceptRole,
        )
        reviewed_btn = None
        if rev_paths and len(rev_paths) != len(all_paths):
            reviewed_btn = box.addButton(
                f"İncelenen gruplara uygula ({format_count(len(reviewed))} grup · "
                f"{format_count(len(rev_paths))} dosya · {format_size(rev_size)})",
                QMessageBox.ButtonRole.AcceptRole,
            )
        here_btn = None
        if here_paths and len(here_paths) != len(all_paths):
            here_btn = box.addButton(
                f"Yalnızca bu grup ({len(here_paths)} dosya · {format_size(here_size)})",
                QMessageBox.ButtonRole.AcceptRole,
            )
        box.addButton("Vazgeç", QMessageBox.ButtonRole.RejectRole)
        all_btn.setEnabled(bool(all_paths))
        box.setDefaultButton(here_btn or reviewed_btn or all_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is all_btn:
            return all_groups
        if reviewed_btn is not None and clicked is reviewed_btn:
            return reviewed
        if here_btn is not None and clicked is here_btn:
            return [self.current_group]
        return None

    def _run_action(self, kind: str) -> None:
        if self._busy or self.scan_thread is not None:
            return
        groups = self._ask_scope(kind)
        if groups is None:
            return
        paths, _size, _skipped = self._collect_marked(groups)
        if not paths:
            QMessageBox.information(self, "BenzerFoto", "İşlenecek dosya yok.")
            return
        if kind == KIND_TRASH:
            unsupported = [p for p in paths if not recycle.is_trash_supported(p)]
            if unsupported:
                sample = "\n".join(unsupported[:5]) + ("\n…" if len(unsupported) > 5 else "")
                QMessageBox.warning(
                    self,
                    "BenzerFoto",
                    f"{len(unsupported)} dosya Geri Dönüşüm Kutusu olmayan bir sürücüde (ağ ya da USB). "
                    "Windows bu dosyaları kalıcı sileceği için işlem yapılmadı.\n\n"
                    f"Bunun yerine “{DUPLICATES_FOLDER_NAME} klasörüne taşı” seçeneğini kullanın.\n\n{sample}",
                )
                return
            work = lambda progress: actions.send_to_trash(self.db_path, paths, progress)  # noqa: E731
            title = "Geri Dönüşüm Kutusu'na gönderiliyor…"
        else:
            roots = self._folders(FOLDER_SCAN)
            work = lambda progress: actions.move_to_duplicates(self.db_path, paths, roots, progress)  # noqa: E731
            title = f"{DUPLICATES_FOLDER_NAME} klasörüne taşınıyor…"
        self._start_job(title, work, lambda result: self._on_action_done(kind, result))

    def _start_job(self, title: str, work, on_done, fail_hint: str = "Geçmiş penceresinden ayrıntıya bakabilirsiniz.") -> None:
        """Dosya işlemini arka planda çalıştırır, ilerleme penceresi gösterir."""
        self._busy = True
        self.scan_button.setEnabled(False)
        self._update_action_buttons()
        dlg = QProgressDialog(title, "", 0, 0, self)
        dlg.setWindowTitle("BenzerFoto")
        dlg.setCancelButton(None)  # yarıda kesilen işlem karışıklık yaratır
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.show()
        self._progress_dialog = dlg
        relay = ProgressRelay(self)
        relay.changed.connect(self._on_job_progress)

        def report(done: int, total: int) -> None:
            if done == total or done % max(1, total // 100) == 0:
                relay.changed.emit(done, total)

        def finish(result) -> None:
            self._end_job()
            on_done(result)

        def fail(message: str) -> None:
            self._end_job()
            QMessageBox.critical(self, "BenzerFoto", f"İşlem tamamlanamadı:\n{message}\n\n{fail_hint}")
            self._refresh_undo_state()

        run_async(lambda: work(report), finish, fail)

    def _on_job_progress(self, done: int, total: int) -> None:
        dlg = self._progress_dialog
        if dlg is not None and total > 0:
            dlg.setMaximum(total)
            dlg.setValue(done)

    def _end_job(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None
        self._busy = False
        self.scan_button.setEnabled(True)
        self._update_action_buttons()

    def _on_action_done(self, kind: str, result: actions.ActionResult) -> None:
        self._apply_removal(set(result.done))
        self._refresh_undo_state()
        where = f"{DUPLICATES_FOLDER_NAME} klasörüne taşındı" if kind == KIND_MOVE else "Geri Dönüşüm Kutusu'na gönderildi"
        text = f"{format_count(len(result.done))} dosya ({format_size(result.done_bytes)}) {where}."
        self.statusBar().showMessage(text + " Geri Al ile geri alabilirsiniz.", 15000)
        if result.failed:
            QMessageBox.warning(self, "BenzerFoto", text + "\n\n" + self._failure_text(result.failed))
        elif result.done:
            QMessageBox.information(self, "BenzerFoto", text + "\n\nGeri Al düğmesiyle geri alabilirsiniz.")

    @staticmethod
    def _failure_text(failed: list[tuple[str, str]]) -> str:
        lines = [f"• {os.path.basename(p)}: {err}" for p, err in failed[:10]]
        more = f"\n… ve {len(failed) - 10} dosya daha" if len(failed) > 10 else ""
        return f"{len(failed)} dosya işlenemedi:\n" + "\n".join(lines) + more

    def _apply_removal(self, removed: set[str]) -> None:
        """Taşınan/kutuya giden dosyaları gruplardan çıkarır; elle yapılan işaretler korunur."""
        if not removed:
            return
        self.features = [f for f in self.features if f.path not in removed]
        protected = self._folders(FOLDER_PROTECT)
        for kind, groups in self.groups_by_kind.items():
            kept = []
            for g in groups:
                if any(m.path in removed for m in g.members):
                    g.members = [m for m in g.members if m.path not in removed]
                    g.marked -= removed
                    g.protected -= removed
                    if len(g.members) < 2:
                        continue
                    if g.best_path in removed:
                        choose_best(g, protected)
                kept.append(g)
            self.groups_by_kind[kind] = kept
        previous = self.current_group
        self._update_mode_labels()
        self._apply_filter(keep_row=True)
        if previous is not None and self.current_group is previous:
            self._show_group(previous)  # kartları yenile
        self._update_cache_status()

    def _refresh_undo_state(self) -> None:
        try:
            with Journal(self.db_path) as journal:
                self._last_undoable = journal.last_undoable()
        except Exception:  # günlük okunamazsa geri alma kapalı kalır
            self._last_undoable = None
        op = self._last_undoable
        if op is None:
            self.undo_button.setToolTip("Geri alınacak işlem yok")
        else:
            self.undo_button.setToolTip(
                f"Son işlemi geri al: {op.created_at} · {op.label} · {format_count(op.done_count)} dosya"
            )
        self._update_action_buttons()

    def _undo_last(self) -> None:
        if self._last_undoable is not None:
            self._undo_operation(self._last_undoable.id)

    def _undo_operation(self, op_id: int) -> None:
        if self._busy or self.scan_thread is not None:
            return
        with Journal(self.db_path) as journal:
            op = journal.get(op_id)
        if op is None or not op.undoable:
            QMessageBox.information(self, "BenzerFoto", "Bu işlem zaten geri alınmış.")
            self._refresh_undo_state()
            return
        answer = QMessageBox.question(
            self,
            "BenzerFoto",
            f"Bu işlem geri alınsın mı?\n\n{op.created_at} · {op.label}\n"
            f"{format_count(op.done_count)} dosya · {format_size(op.done_bytes)}\n\n"
            "Dosyalar özgün klasörlerine geri konur. Özgün yerde aynı adlı bir dosya varsa "
            "üzerine yazılmaz, o dosya atlanır.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        db_path = self.db_path

        def work(progress):
            result = actions.undo(db_path, op_id, progress)
            with FeatureCache(db_path) as cache:
                feats = cache.get_features(result.done)
            return result, feats

        self._start_job("Geri alınıyor…", work, self._on_undo_done)

    def _on_undo_done(self, payload) -> None:
        result, feats = payload
        self._refresh_undo_state()
        text = f"{format_count(len(result.done))} dosya ({format_size(result.done_bytes)}) özgün yerine geri kondu."
        if self.features and result.done:
            known = {f.path for f in self.features}
            self.features.extend(f for f in feats if f.path not in known)
            self._update_cache_status()
            self._regroup_all()
            text += "\nGruplar yeniden hesaplandı."
            if len(feats) < len(result.done):
                text += f"\n{len(result.done) - len(feats)} dosya önbellekte yok; görmek için yeniden TARA'ya basın."
        elif result.done:
            text += "\nGrupları görmek için TARA'ya basın."
        self.statusBar().showMessage(text.splitlines()[0], 15000)
        if result.failed:
            QMessageBox.warning(
                self, "BenzerFoto", text + "\n\n" + self._failure_text(result.failed) + "\n\nGeri alma daha sonra yeniden denenebilir."
            )
        else:
            QMessageBox.information(self, "BenzerFoto", text)

    def _show_history(self) -> None:
        dlg = HistoryDialog(self.db_path, self)
        dlg.exec()
        if dlg.requested_undo is not None:
            self._undo_operation(dlg.requested_undo)
        else:
            self._refresh_undo_state()

    # ------------------------------------------------------------------
    # Rapor ve Ayarlar penceresi (5. aşama)
    # ------------------------------------------------------------------

    def report_groups(self) -> list[PhotoGroup]:
        """Rapora girecek gruplar: seçili moddaki tümü, ekrandaki sıralamayla."""
        groups = list(self.groups_by_kind[self.current_kind()])
        self._sort_groups(groups)
        return groups

    def _export_report(self) -> None:
        groups = self.report_groups()
        if not self._is_idle() or not groups:
            return
        folder = Path(self.settings.value("report_dir", str(Path.home())))
        start = str(folder / f"BenzerFoto-rapor-{self.current_kind().value}")
        path, selected = QFileDialog.getSaveFileName(
            self, "Raporu kaydet", start, f"{REPORT_FILTER_HTML};;{REPORT_FILTER_CSV}"
        )
        if not path:
            return
        if Path(path).suffix.lower() not in (".html", ".htm", ".csv"):
            path += ".csv" if selected == REPORT_FILTER_CSV else ".html"
        self.settings.setValue("report_dir", str(Path(path).parent))
        self.export_report_to(path, groups)

    def export_report_to(self, path: str, groups: list[PhotoGroup] | None = None) -> None:
        """Raporu arka planda yazar; bitince haber verir. Tarama ya da işlem sürerken çalışmaz."""
        if not self._is_idle():
            return
        groups = self.report_groups() if groups is None else groups
        self._start_job(
            "Rapor hazırlanıyor…",
            lambda progress: report.write_report(groups, path, progress),
            lambda count: self._on_report_done(path, count),
            fail_hint="Rapor kaydedilemedi. Başka bir klasör seçip yeniden deneyin.",
        )

    def _on_report_done(self, path: str, count: int) -> None:
        self.statusBar().showMessage(f"Rapor kaydedildi: {path}", 15000)
        box = QMessageBox(self)
        box.setWindowTitle("BenzerFoto")
        box.setText(f"Rapor kaydedildi ({format_count(count)} dosya).")
        box.setInformativeText(path)
        open_btn = box.addButton("Raporu aç", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_shortcuts(self) -> None:
        ShortcutsDialog(self).exec()

    def _show_settings(self) -> None:
        dlg = SettingsDialog(self.app_settings, self)
        if dlg.exec():
            self.apply_app_settings(dlg.values())

    def apply_app_settings(self, new: AppSettings) -> None:
        """Ayarları kaydeder ve eşikleri/zaman penceresini hemen uygular."""
        self.app_settings = new
        new.save(self.settings)
        self.thresholds[GroupKind.SIMILAR] = float(new.similar_threshold)
        self.thresholds[GroupKind.SCENE] = float(new.scene_threshold)
        self.window_combo.blockSignals(True)
        self.window_combo.setCurrentIndex(WINDOW_CHOICES.index(new.scene_window))
        self.window_combo.blockSignals(False)
        self._update_mode_controls()
        if self.features:
            self._regroup_all()

    # ------------------------------------------------------------------
    # Özetler
    # ------------------------------------------------------------------

    def _update_summary(self) -> None:
        group = self.current_group
        groups = self.groups_by_kind[self.current_kind()]
        all_files = sum(len(g.marked) for g in groups)
        all_size = sum(g.marked_size for g in groups)
        here_files = len(group.marked) if group else 0
        here_size = group.marked_size if group else 0
        self.summary_label.setText(
            f"Bu grupta işaretli: <b>{here_files} dosya</b> · <b>{format_size(here_size)}</b>"
            f" &nbsp;<span style='color:#666'>(tüm gruplarda: {format_count(all_files)} dosya · {format_size(all_size)})</span>"
        )
        self._update_action_buttons(all_files)

    def _is_idle(self) -> bool:
        """Ne tarama ne de dosya/rapor işi sürüyor."""
        return not self._busy and self.scan_thread is None

    def _update_action_buttons(self, marked_count: int | None = None) -> None:
        if marked_count is None:
            marked_count = sum(len(g.marked) for g in self.groups_by_kind[self.current_kind()])
        idle = self._is_idle()
        for b in (self.move_button, self.trash_button):
            b.setEnabled(idle and marked_count > 0)
        self.history_button.setEnabled(not self._busy)
        self.report_button.setEnabled(idle and bool(self.groups_by_kind[self.current_kind()]))
        self.undo_button.setEnabled(idle and self._last_undoable is not None)

    def _update_cache_status(self) -> None:
        self.cache_status.setText(f"Önbellek: {self.db_path.name} · {format_count(len(self.features))} fotoğraf")
        self.cache_status.setToolTip(str(self.db_path))

    def _update_rule_status(self) -> None:
        protected = self._folders(FOLDER_PROTECT)
        if protected:
            names = ", ".join(f"“{p}”" for p in protected[:2]) + (" …" if len(protected) > 2 else "")
            self.rule_status.setText(f"Koruma kuralı: {names} her zaman korunur")
        else:
            self.rule_status.setText("Koruma kuralı yok")

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ------------------------------------------------------------------
    # Ayarlar
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self.settings
        for entry in s.value("folders", [], type=list) or []:
            kind, _, path = str(entry).partition("|")
            if kind in FOLDER_ICONS and path:
                self._append_folder(path, kind)
        self.recursive_box.setChecked(s.value("recursive", True, type=bool))
        mode =s.value("mode", GroupKind.SCENE.value)
        for kind, btn in self.mode_buttons.items():
            if kind.value == mode:
                btn.setChecked(True)
        for name, box in self.format_boxes.items():
            box.setChecked(s.value(f"format_{name}", True, type=bool))
        geometry = s.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._update_rule_status()
        self._update_cache_status()

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue(
            "folders",
            [f"{self.folder_list.item(i).data(ROLE_KIND)}|{self.folder_list.item(i).data(Qt.ItemDataRole.UserRole)}" for i in range(self.folder_list.count())],
        )
        s.setValue("recursive", self.recursive_box.isChecked())
        s.setValue("mode", self.current_kind().value)
        for name, box in self.format_boxes.items():
            s.setValue(f"format_{name}", box.isChecked())
        self._update_rule_status()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            # Yarıda kalan dosya işlemi günlükle diskin uyuşmamasına yol açabilir
            QMessageBox.information(self, "BenzerFoto", "Dosya işlemi sürüyor, bitince kapatabilirsiniz.")
            event.ignore()
            return
        if self.scan_thread is not None:
            self.scan_thread.cancel()
            self.scan_thread.wait()
        self.settings.setValue("geometry", self.saveGeometry())
        self._save_settings()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)
