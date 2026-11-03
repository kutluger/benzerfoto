"""Ayarlar penceresi: varsayılan eşikler, aynı sahne zaman penceresi, işçi sayısı."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from benzerfoto.config import DUPLICATES_FOLDER_NAME
from benzerfoto.scanner import default_workers
from benzerfoto.settings import MAX_WORKERS, THRESHOLD_RANGE, WINDOW_CHOICES, AppSettings


def window_text(seconds: int) -> str:
    return f"{seconds} sn" if seconds < 120 else f"{seconds // 60} dk"


class SettingsDialog(QDialog):
    def __init__(self, current: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar — BenzerFoto")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.similar_spin = self._percent_spin()
        self.scene_spin = self._percent_spin()
        form.addRow("Benzer görüntü eşiği:", self.similar_spin)
        form.addRow("Aynı sahne eşiği:", self.scene_spin)
        self.window_combo = QComboBox()
        for sec in WINDOW_CHOICES:
            self.window_combo.addItem(window_text(sec), sec)
        form.addRow("Aynı sahne zaman penceresi:", self.window_combo)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, MAX_WORKERS)
        self.workers_spin.setSpecialValueText(f"Otomatik ({default_workers()})")
        self.workers_spin.setToolTip("Taramada aynı anda çalışacak süreç sayısı. Otomatik: çekirdek sayısının bir eksiği.")
        form.addRow("Tarama işçi sayısı:", self.workers_spin)
        folder = QLabel(f"<b>{DUPLICATES_FOLDER_NAME}</b> (değiştirilemez)")
        form.addRow("Taşıma klasörü:", folder)
        lay.addLayout(form)

        note = QLabel(
            "Eşikler ve zaman penceresi uygulama her açıldığında bu değerlerle başlar; "
            "Tamam'a basınca hemen de uygulanır. Ana penceredeki kaydırıcı yalnızca o oturumu etkiler."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Tamam")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        restore = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        restore.setText("Fabrika değerleri")
        restore.clicked.connect(lambda: self.set_values(AppSettings()))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.set_values(current)

    @staticmethod
    def _percent_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(*THRESHOLD_RANGE)
        spin.setPrefix("%")
        spin.setToolTip("Yüzde arttıkça eşleşme katılaşır")
        return spin

    def set_values(self, s: AppSettings) -> None:
        self.similar_spin.setValue(s.similar_threshold)
        self.scene_spin.setValue(s.scene_threshold)
        self.window_combo.setCurrentIndex(WINDOW_CHOICES.index(s.scene_window))
        self.workers_spin.setValue(s.workers)

    def values(self) -> AppSettings:
        return AppSettings(
            similar_threshold=self.similar_spin.value(),
            scene_threshold=self.scene_spin.value(),
            scene_window=self.window_combo.currentData(),
            workers=self.workers_spin.value(),
        )
