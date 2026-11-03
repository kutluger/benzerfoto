"""Grubun tamamını gönderme için ikinci (açık onaylı) pencere."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DiscardGroupDialog(QDialog):
    """Kullanıcı kutuyu işaretlemeden "Gönder" düğmesi açılmaz."""

    def __init__(self, count: int, size_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Son onay")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel(f"<b>{count} fotoğrafın tamamı</b> ({size_text}) Geri Dönüşüm Kutusu'na gönderilecek.")
        title.setWordWrap(True)
        layout.addWidget(title)
        info = QLabel(
            "Bu gruptan hiçbir fotoğraf tutulmayacak. Dosyalar silinmez; Geri Dönüşüm Kutusu "
            "boşaltılmadığı sürece Geri Al ya da Geçmiş penceresinden geri getirilebilir."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        self.confirm_box = QCheckBox("Evet, bu gruptaki fotoğrafların hiçbirini tutmak istemiyorum")
        layout.addWidget(self.confirm_box)

        buttons = QDialogButtonBox()
        self.send_button = QPushButton("🗑 Tamamını gönder")
        self.send_button.setEnabled(False)
        buttons.addButton(self.send_button, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton("Vazgeç", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setDefault(True)  # yanlışlıkla Enter'a basılırsa hiçbir şey olmasın
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.confirm_box.toggled.connect(self.send_button.setEnabled)
        layout.addWidget(buttons)
