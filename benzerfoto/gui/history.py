"""İşlem geçmişi penceresi: yapılan taşıma ve geri dönüşüm işlemleri."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from benzerfoto.formatting import format_count, format_size
from benzerfoto.journal import DONE, FAILED, RESTORE_FAILED, RESTORED, Journal, Operation

STATUS_TEXT = {
    DONE: "Yapıldı",
    FAILED: "Başarısız",
    RESTORED: "Geri alındı",
    RESTORE_FAILED: "Geri alınamadı",
}


def _cell(text: str, tip: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if tip:
        item.setToolTip(tip)
    return item


class HistoryDialog(QDialog):
    """İşlemleri ve her işlemdeki dosyaları listeler. Seçilen işlem geri alınabilir.

    Geri alma isteği `requested_undo` ile pencere kapandıktan sonra ana pencereye iletilir.
    """

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İşlem geçmişi")
        self.resize(1000, 620)
        self.db_path = db_path
        self.requested_undo: int | None = None
        self.operations: list[Operation] = []

        lay = QVBoxLayout(self)
        hint = QLabel("Her taşıma ve geri dönüşüm işlemi burada kayıtlıdır. Geri alınan dosyalar özgün klasörlerine döner.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.op_table = QTableWidget(0, 5)
        self.op_table.setHorizontalHeaderLabels(["Tarih", "İşlem", "Dosya", "Boyut", "Durum"])
        self.op_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.op_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.op_table.verticalHeader().setVisible(False)
        self.op_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.op_table.itemSelectionChanged.connect(self._on_selected)
        splitter.addWidget(self.op_table)

        self.item_table = QTableWidget(0, 4)
        self.item_table.setHorizontalHeaderLabels(["Dosya", "Özgün yer", "Taşındığı yer", "Durum"])
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.item_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.item_table)
        splitter.setSizes([260, 300])
        lay.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        buttons.addWidget(self.summary, 1)
        self.undo_button = QPushButton("↶ Seçili işlemi geri al")
        self.undo_button.clicked.connect(self._request_undo)
        close = QPushButton("Kapat")
        close.clicked.connect(self.reject)
        buttons.addWidget(self.undo_button)
        buttons.addWidget(close)
        lay.addLayout(buttons)

        self._load()

    def _load(self) -> None:
        try:
            with Journal(self.db_path) as journal:
                self.operations = journal.operations(500)
        except Exception as exc:  # günlük okunamadı
            self.operations = []
            self.summary.setText(f"Günlük okunamadı: {exc}")
        self.op_table.setRowCount(len(self.operations))
        for row, op in enumerate(self.operations):
            if op.undone_at:
                status = f"Geri alındı ({op.undone_at})"
            elif op.done_count:
                status = "Geri alınabilir"
            else:
                status = "Dosya işlenmedi"
            if op.failed_count:
                status += f" · {op.failed_count} dosya başarısız"
            self.op_table.setItem(row, 0, _cell(op.created_at))
            self.op_table.setItem(row, 1, _cell(op.label))
            self.op_table.setItem(row, 2, _cell(format_count(op.done_count)))
            self.op_table.setItem(row, 3, _cell(format_size(op.done_bytes)))
            self.op_table.setItem(row, 4, _cell(status))
        self.op_table.resizeColumnsToContents()
        if not self.operations:
            self.summary.setText(self.summary.text() or "Henüz işlem yapılmadı.")
        self.undo_button.setEnabled(False)
        if self.operations:
            self.op_table.selectRow(0)

    def _selected(self) -> Operation | None:
        rows = self.op_table.selectionModel().selectedRows()
        return self.operations[rows[0].row()] if rows else None

    def _on_selected(self) -> None:
        op = self._selected()
        self.undo_button.setEnabled(op is not None and op.undoable)
        if op is None:
            self.item_table.setRowCount(0)
            return
        with Journal(self.db_path) as journal:
            items = journal.items(op.id)
        self.item_table.setRowCount(len(items))
        for row, it in enumerate(items):
            status = STATUS_TEXT.get(it.status, it.status)
            self.item_table.setItem(row, 0, _cell(os.path.basename(it.src), it.src))
            self.item_table.setItem(row, 1, _cell(os.path.dirname(it.src), it.src))
            dst = it.dst or ("Geri Dönüşüm Kutusu" if it.status != FAILED else "")
            self.item_table.setItem(row, 2, _cell(dst, it.dst))
            self.item_table.setItem(row, 3, _cell(f"{status}: {it.error}" if it.error else status, it.error))
        self.item_table.resizeColumnToContents(0)
        self.item_table.resizeColumnToContents(3)
        self.summary.setText(f"{op.created_at} · {op.label} · {format_count(len(items))} kayıt")

    def _request_undo(self) -> None:
        op = self._selected()
        if op is not None and op.undoable:
            self.requested_undo = op.id
            self.accept()
