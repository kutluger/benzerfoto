"""Uygulamanın görünümü (Qt stil sayfası). Renkler onaylanan tasarım taslağından."""

ACCENT = "#2563eb"
STAR = "#f59e0b"
DANGER = "#dc2626"
OK = "#16a34a"

# Grup türü etiketlerinin renkleri: (arka plan, yazı)
TAG_COLORS = {
    "exact": ("#fee2e2", "#991b1b"),
    "similar": ("#fef3c7", "#92400e"),
    "scene": ("#dbeafe", "#1e40af"),
}

def apply_theme(app) -> None:
    """Uygulamaya açık temayı ve stil sayfasını uygular.

    Arayüz açık renkler için tasarlandı. Windows koyu temadayken Qt koyu bir
    palet seçer; stil sayfasının değinmediği yerler (menü, iletişim pencereleri)
    koyu zemin üstünde koyu yazıyla okunmaz olur. Bu yüzden açık tema zorlanır.
    """
    from PySide6.QtCore import Qt

    app.setStyle("Fusion")  # her Windows sürümünde aynı görünüm
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+
        hints.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
QMainWindow, QWidget#centralArea {{ background: #f3f3f3; }}
QWidget {{ font-size: 13px; color: #1f2328; }}

QFrame#leftPanel, QFrame#midPanel {{ background: #ffffff; border-right: 1px solid #dddddd; }}
QFrame#rightPanel {{ background: #fafafa; }}
QFrame#rightHeader, QFrame#bottomBar {{ background: #ffffff; }}
QFrame#rightHeader {{ border-bottom: 1px solid #dddddd; }}
QFrame#bottomBar {{ border-top: 1px solid #dddddd; }}

QLabel#sectionTitle {{
    font-size: 11px; font-weight: 600; color: #6b7280; letter-spacing: 1px;
}}
QLabel#groupTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ color: #666666; }}
QLabel#kindTag {{ border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600; }}

QListWidget#folderList {{ border: 1px solid #d0d7de; border-radius: 6px; }}
QListWidget#folderList::item {{ padding: 6px 4px; border-bottom: 1px solid #eeeeee; }}
QListWidget#folderList::item:selected {{ background: #eef4ff; color: #1f2328; }}

QListView#groupList {{ border: none; background: #ffffff; outline: 0; }}

QPushButton {{
    background: #f6f8fa; border: 1px solid #c8ced5; border-radius: 5px; padding: 5px 10px;
}}
QPushButton:hover {{ background: #eef1f4; }}
QPushButton:disabled {{ color: #9aa0a6; background: #f6f8fa; }}
QPushButton#scanButton {{
    background: {ACCENT}; color: white; border: none; border-radius: 6px;
    padding: 11px; font-size: 15px; font-weight: 600;
}}
QPushButton#scanButton:hover {{ background: #1d4ed8; }}
QPushButton#scanButton[running="true"] {{ background: {DANGER}; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QPushButton#primary:disabled {{ background: #93b4f5; color: #eef4ff; border-color: #93b4f5; }}
QPushButton#chip {{ border-radius: 11px; padding: 3px 10px; background: #ffffff; border: 1px solid #d0d7de; }}
QPushButton#chip:checked {{ background: #1f2328; color: white; border-color: #1f2328; }}

QRadioButton {{ padding: 5px 6px; border-radius: 6px; }}
QRadioButton:checked {{ background: #eef4ff; font-weight: 600; }}

QSlider:horizontal {{ min-height: 30px; }}
QSlider::groove:horizontal {{ height: 6px; background: #e5e7eb; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: white; border: 2px solid {ACCENT}; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 9px;
}}
QSlider::sub-page:horizontal:disabled {{ background: #c7c9cc; }}
QSlider::handle:horizontal:disabled {{ border-color: #c7c9cc; }}

QProgressBar {{ border: none; background: #e5e7eb; border-radius: 4px; height: 8px; }}
QProgressBar::chunk {{ background: {OK}; border-radius: 4px; }}

QLineEdit, QComboBox {{ border: 1px solid #d0d7de; border-radius: 5px; padding: 4px 6px; background: white; }}

QFrame#card {{ background: white; border: 1px solid #d0d7de; border-radius: 8px; }}
QFrame#card[best="true"] {{ border: 2px solid {STAR}; }}
QFrame#card[focused="true"] {{ border: 2px solid {ACCENT}; }}
QFrame#card[best="true"][focused="true"] {{ border: 2px solid {ACCENT}; }}
QLabel#cardImage {{ background: #eceff3; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
QLabel#cardName {{ font-weight: 600; font-size: 12px; }}
QLabel#cardMeta {{ font-size: 11px; color: #444444; }}
QLabel#starBadge {{
    background: {STAR}; color: white; font-weight: 700; border-radius: 9px; padding: 1px 8px; font-size: 12px;
}}
QLabel#shieldBadge {{
    background: {OK}; color: white; font-weight: 700; border-radius: 9px; padding: 1px 8px; font-size: 12px;
}}
QCheckBox#markBox::indicator {{ width: 20px; height: 20px; }}
QCheckBox#markBox::indicator:unchecked {{ background: white; border: 2px solid #666666; border-radius: 4px; }}
QCheckBox#markBox::indicator:checked {{
    background: {DANGER}; border: 2px solid {DANGER}; border-radius: 4px;
    image: none;
}}
QCheckBox#markBox::indicator:disabled {{ background: #e5e7eb; border: 2px solid #c7c9cc; border-radius: 4px; }}

QProgressBar#sharpBar {{ height: 4px; border-radius: 2px; }}
QProgressBar#sharpBar::chunk {{ border-radius: 2px; }}
QProgressBar#sharpBar[level="low"]::chunk {{ background: {DANGER}; }}
QProgressBar#sharpBar[level="mid"]::chunk {{ background: {STAR}; }}
QProgressBar#sharpBar[level="high"]::chunk {{ background: {OK}; }}

QFrame#previewFrame {{ background: white; border: 1px solid #d0d7de; border-radius: 8px; }}
QGraphicsView#previewView {{ background: #222222; border: none; }}
QLabel#zoomBadge {{ background: rgba(0,0,0,150); color: white; border-radius: 6px; padding: 3px 9px; font-size: 12px; }}

/* Açılır menüler ve ipuçları: Windows koyu temada da okunur kalsın */
QMenu {{ background: #ffffff; color: #1f2328; border: 1px solid #c8ced5; border-radius: 6px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px 6px 12px; border-radius: 4px; background: transparent; }}
QMenu::item:selected {{ background: #eef4ff; color: #1f2328; }}
QMenu::item:disabled {{ color: #9aa0a6; }}
QMenu::separator {{ height: 1px; background: #e5e7eb; margin: 4px 6px; }}
QToolTip {{ background: #ffffff; color: #1f2328; border: 1px solid #c8ced5; padding: 4px 6px; }}

QStatusBar {{ background: #f0f0f0; border-top: 1px solid #dddddd; color: #555555; font-size: 12px; }}
QSplitter::handle {{ background: transparent; }}
"""
