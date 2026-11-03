"""Klavye kısayolları yardım penceresi (F1)."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

# (tuş, açıklama) — ana penceredeki kısayollarla aynı tutulmalı
SHORTCUTS: list[tuple[str, str]] = [
    ("Enter", "Grubu incelendi olarak işaretle ve sonraki gruba geç"),
    ("Page Down  /  Ctrl+→", "Sonraki grup (geçilen grup incelendi sayılır)"),
    ("Page Up  /  Ctrl+←", "Önceki grup"),
    ("→  /  ←", "Gruptaki sonraki / önceki fotoğraf"),
    ("Boşluk", "Seçili fotoğrafın işaretini aç / kapat"),
    ("Delete", "Seçili fotoğrafı onay sorarak Geri Dönüşüm Kutusu'na gönder"),
    ("Çift tık (kart)", "İşareti aç / kapat"),
    ("Sağ tık (kart)", "Bunu tut · Dosya konumunu aç (fotoğraf seçili gelir) · Grubun tamamını gönder"),
    ("Tekerlek (önizleme)", "Yakınlaştır / uzaklaştır; çift tık pencereye sığdırır"),
    ("F1", "Bu pencere"),
]


def shortcuts_html() -> str:
    rows = "".join(
        f"<tr><td style='padding:5px 18px 5px 0; white-space:nowrap;'><b>{escape(key)}</b></td>"
        f"<td style='padding:5px 0;'>{escape(text)}</td></tr>"
        for key, text in SHORTCUTS
    )
    return (
        f"<table cellspacing='0'>{rows}</table>"
        "<p style='color:#666666;'>Arama kutusuna yazarken kısayollar çalışmaz. "
        "Hiçbir işlem dosyayı kalıcı silmez; Geri Al her zaman mümkündür.</p>"
    )


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Klavye kısayolları")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        self.label = QLabel(shortcuts_html())
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Kapat")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
