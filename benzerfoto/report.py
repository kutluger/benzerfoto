"""Bulunan grupları dışa aktarma: Excel'de açılan CSV ve tek dosyalı HTML raporu.

Bu modül Qt kullanmaz; arka plandaki iş parçacığında çalışabilir ve doğrudan
test edilebilir. Küçük resimler Pillow ile üretilir ve HTML'in içine gömülür,
böylece rapor internet bağlantısı olmadan, tek dosya olarak açılır.
"""

from __future__ import annotations

import base64
import csv
import html
import io
import os
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from PIL import Image, ImageOps

from benzerfoto import __version__
from benzerfoto.features import ImageFeatures  # içe aktarılınca HEIC açıcısı da kaydolur
from benzerfoto.formatting import format_count, format_date, format_size
from benzerfoto.grouping import PhotoGroup

STATUS_BEST = "★ Önerilen"
STATUS_MARKED = "İşaretli"
STATUS_PROTECTED = "Korunan"
STATUS_KEEP = "Tutulacak"

CSV_HEADER = ["Tür", "Grup No", "Durum", "Yol", "Boyut (bayt)", "Boyut", "Çözünürlük", "Çekim zamanı", "Netlik"]
THUMB_SIZE = 160

ProgressCallback = Callable[[int, int], None]


@dataclass
class ReportRow:
    """Rapordaki tek dosya satırı."""

    kind: str
    group_no: int
    status: str
    path: str
    size: int
    resolution: str
    taken_at: str
    sharpness: str


def member_status(group: PhotoGroup, path: str) -> str:
    if path == group.best_path:
        return STATUS_BEST
    if path in group.marked:
        return STATUS_MARKED
    if path in group.protected:
        return STATUS_PROTECTED
    return STATUS_KEEP


def ordered_members(group: PhotoGroup) -> list[ImageFeatures]:
    """Önerilen kare başta, diğerleri gruptaki sırasıyla."""
    return sorted(group.members, key=lambda m: m.path != group.best_path)


def resolution_text(m: ImageFeatures) -> str:
    return f"{m.width} × {m.height}" if m.width and m.height else "—"


def build_rows(groups: Sequence[PhotoGroup]) -> list[ReportRow]:
    """Her grubun üyelerini, önerilen kare başta olacak şekilde satırlara çevirir."""
    rows: list[ReportRow] = []
    for no, group in enumerate(groups, start=1):
        for m in ordered_members(group):
            rows.append(
                ReportRow(
                    kind=group.kind.label,
                    group_no=no,
                    status=member_status(group, m.path),
                    path=m.path,
                    size=m.size,
                    resolution=resolution_text(m),
                    taken_at=format_date(m.taken_at) if m.taken_at else "—",
                    # Türkçe Excel ondalık ayırıcı olarak virgül bekler
                    sharpness=f"{m.sharpness:.1f}".replace(".", ",") if m.sharpness is not None else "—",
                )
            )
    return rows


@contextmanager
def _atomic_write(path: str | os.PathLike, **open_args) -> Iterator[TextIO]:
    """Önce geçici dosyaya yazar, bitince yerine koyar: hata olursa yarım rapor kalmaz."""
    tmp = Path(f"{os.fspath(path)}.tmp")
    try:
        with open(tmp, "w", **open_args) as f:
            yield f
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_csv(groups: Sequence[PhotoGroup], path: str | os.PathLike) -> int:
    """CSV yazar ve satır sayısını döndürür.

    UTF-8 BOM ve `;` ayırıcı, Excel'in Türkçe karakterleri ve sütunları doğru
    tanıması içindir.
    """
    rows = build_rows(groups)
    with _atomic_write(path, encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(CSV_HEADER)
        for r in rows:
            writer.writerow(
                [r.kind, r.group_no, r.status, r.path, r.size, format_size(r.size), r.resolution, r.taken_at, r.sharpness]
            )
    return len(rows)


def make_thumbnail_data_uri(path: str, size: int = THUMB_SIZE) -> str | None:
    """Küçük JPEG üretip `data:` adresi olarak döndürür; okunamazsa None."""
    try:
        with Image.open(path) as img:
            img.draft("RGB", (size, size))
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((size, size), Image.Resampling.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=72)
    except Exception:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


_STATUS_CLASS = {STATUS_BEST: "best", STATUS_MARKED: "marked", STATUS_PROTECTED: "protected", STATUS_KEEP: "keep"}

_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"

_CSS = """
body{font-family:"Segoe UI",system-ui,sans-serif;margin:0;background:#f5f5f7;color:#222}
header{background:#fff;padding:20px 28px;border-bottom:1px solid #e3e3e3}
h1{margin:0 0 6px;font-size:22px}
.meta{color:#666;font-size:14px}
main{padding:20px 28px}
section{background:#fff;border:1px solid #e3e3e3;border-radius:10px;margin-bottom:18px;padding:14px 16px}
h2{font-size:16px;margin:0 0 12px}
h2 small{color:#777;font-weight:normal}
.cards{display:flex;flex-wrap:wrap;gap:12px}
.card{width:200px;border:2px solid #e3e3e3;border-radius:8px;padding:8px;font-size:12px;word-break:break-all}
.card.best{border-color:#2e9e5b}.card.marked{border-color:#d9534f}.card.protected{border-color:#3b7dd8}
.thumb{width:184px;height:140px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:4px;overflow:hidden}
.thumb img{max-width:100%;max-height:100%}
.tag{display:inline-block;margin:6px 0 4px;padding:1px 8px;border-radius:10px;font-weight:600;background:#eee}
.best .tag{background:#e3f5ea;color:#1e7a44}.marked .tag{background:#fbe5e4;color:#b02a25}
.protected .tag{background:#e3eefb;color:#245fae}
.name{font-weight:600}.path{color:#777}
"""


def _card(m: ImageFeatures, group: PhotoGroup, thumb: str | None) -> str:
    status = member_status(group, m.path)
    esc = html.escape
    image = f'<img src="{thumb}" alt="">' if thumb else "<span>önizleme yok</span>"
    res = resolution_text(m)
    sharp = f"{m.sharpness:.0f}" if m.sharpness is not None else "—"
    return (
        f'<div class="card {_STATUS_CLASS[status]}"><div class="thumb">{image}</div>'
        f'<div class="tag">{esc(status)}</div>'
        f'<div class="name">{esc(os.path.basename(m.path))}</div>'
        f'<div class="path">{esc(os.path.dirname(m.path))}</div>'
        f"<div>{esc(format_size(m.size))} · {esc(res)}</div>"
        f"<div>Çekim: {esc(format_date(m.taken_at))} · Netlik: {sharp}</div></div>"
    )


def write_html(
    groups: Sequence[PhotoGroup],
    path: str | os.PathLike,
    progress: ProgressCallback | None = None,
    thumbnail: Callable[[str], str | None] = make_thumbnail_data_uri,
) -> int:
    """Tek dosyalı HTML raporu yazar ve dosya sayısını döndürür."""
    total = sum(len(g.members) for g in groups)
    notify = progress or (lambda _d, _t: None)
    marked_files = sum(len(g.marked) for g in groups)
    marked_size = sum(g.marked_size for g in groups)
    # Büyük arşivlerde rapor yüzlerce MB olabilir: bellekte toplanmaz, dosyaya akıtılır
    with _atomic_write(path, encoding="utf-8") as f:
        f.write(
            '<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            # Sayfa hiçbir dış kaynak ya da betik yükleyemez; yalnızca gömülü görseller
            f'<meta http-equiv="Content-Security-Policy" content="{_CSP}">'
            f"<title>BenzerFoto raporu</title><style>{_CSS}</style></head><body>"
            "<header><h1>BenzerFoto raporu</h1>"
            f'<div class="meta">{datetime.now():%d.%m.%Y %H:%M} · {format_count(len(groups))} grup · '
            f"{format_count(total)} dosya · işaretli: {format_count(marked_files)} dosya ({format_size(marked_size)})"
            f" · BenzerFoto {__version__}</div></header><main>"
        )
        done = 0
        for no, group in enumerate(groups, start=1):
            f.write(
                f"<section><h2>Grup #{no} · {html.escape(group.kind.label)} "
                f"<small>{len(group.members)} fotoğraf · {format_size(group.total_size)}</small></h2><div class=\"cards\">"
            )
            for m in ordered_members(group):
                f.write(_card(m, group, thumbnail(m.path)))
                done += 1
                notify(done, total)
            f.write("</div></section>")
        f.write("</main></body></html>")
    return total


def write_report(groups: Iterable[PhotoGroup], path: str | os.PathLike, progress: ProgressCallback | None = None) -> int:
    """Uzantıya göre CSV ya da HTML yazar."""
    groups = list(groups)
    if Path(path).suffix.lower() == ".csv":
        return write_csv(groups, path)
    return write_html(groups, path, progress)
