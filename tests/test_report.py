"""Rapor dışa aktarma: CSV ve tek dosyalı HTML."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
from PIL import Image

from benzerfoto.cache import FeatureCache
from benzerfoto.grouping import GroupKind, PhotoGroup, build_groups
from benzerfoto.report import (
    STATUS_BEST,
    STATUS_KEEP,
    STATUS_MARKED,
    STATUS_PROTECTED,
    build_rows,
    make_thumbnail_data_uri,
    write_csv,
    write_html,
    write_report,
)
from benzerfoto.scanner import scan
from tests.conftest import make_scene, save_jpeg


def _groups(tmp_path: Path) -> list[PhotoGroup]:
    root = tmp_path / "arşiv"
    for i in range(3):
        save_jpeg(make_scene(1, shift=i * 8), root / f"Çekim_{i}.jpg", f"2025:08:14 18:42:{10 + i * 5:02}")
    with FeatureCache(tmp_path / "db.sqlite") as cache:
        features = scan([root], cache, workers=1).features
    groups = build_groups(features, GroupKind.SCENE)
    assert len(groups) == 1
    return groups


def test_rows_have_status_and_details(tmp_path: Path):
    group = _groups(tmp_path)[0]
    others = [m.path for m in group.members if m.path != group.best_path]
    group.marked = {others[0]}
    group.protected = {others[1]}
    rows = build_rows([group])
    assert [r.group_no for r in rows] == [1, 1, 1]
    status = {r.path: r.status for r in rows}
    assert status[group.best_path] == STATUS_BEST
    assert status[others[0]] == STATUS_MARKED
    assert status[others[1]] == STATUS_PROTECTED
    assert rows[0].status == STATUS_BEST  # önerilen kare ilk sırada
    assert all(r.kind == "Aynı sahne" and r.resolution == "800 × 600" for r in rows)

    group.protected = set()
    assert {r.status for r in build_rows([group])} == {STATUS_BEST, STATUS_MARKED, STATUS_KEEP}


def test_csv_has_bom_and_opens_with_turkish(tmp_path: Path):
    groups = _groups(tmp_path)
    out = tmp_path / "rapor.csv"
    write_csv(groups, out)
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with open(out, encoding="utf-8-sig", newline="") as f:
        table = list(csv.reader(f, delimiter=";"))
    assert table[0][:4] == ["Tür", "Grup No", "Durum", "Yol"]
    assert len(table) == 4
    assert any("çekim_" in row[3].lower() and "arşiv" in row[3].lower() for row in table[1:])
    assert table[1][4].isdigit()  # bayt sütunu Excel'de sayı olarak sıralanabilsin


def test_html_is_self_contained(tmp_path: Path):
    groups = _groups(tmp_path)
    out = tmp_path / "rapor.html"
    calls = []
    write_html(groups, out, progress=lambda d, t: calls.append((d, t)))
    text = out.read_text(encoding="utf-8")
    assert text.count("data:image/jpeg;base64,") == 3
    assert not re.search(r"(src|href)=\"https?://", text)  # internetsiz açılır
    assert "<script" not in text
    assert "çekim_0.jpg" in text.lower()
    assert calls[-1] == (3, 3)


def test_html_escapes_paths_and_survives_broken_image(tmp_path: Path):
    group = _groups(tmp_path)[0]
    # Windows'ta bu adla dosya açılamaz: hem kaçış hem okunamayan görsel denenir
    group.members[1].path = str(tmp_path / "<i>&kötü.jpg")
    out = tmp_path / "rapor.html"
    write_html([group], out)
    text = out.read_text(encoding="utf-8")
    assert "<i>" not in text
    assert "&lt;i&gt;&amp;kötü.jpg" in text
    assert text.count("data:image/jpeg;base64,") == 2


def test_thumbnail_is_small(tmp_path: Path):
    path = tmp_path / "buyuk.png"
    Image.new("RGB", (3000, 2000), (10, 120, 200)).save(path)
    uri = make_thumbnail_data_uri(str(path), 160)
    assert uri is not None and uri.startswith("data:image/jpeg;base64,")
    assert len(uri) < 20_000
    assert make_thumbnail_data_uri(str(tmp_path / "yok.jpg")) is None


def test_write_report_picks_format_by_extension(tmp_path: Path):
    groups = _groups(tmp_path)
    for name, is_csv in (("a.CSV", True), ("b.HTML", False), ("c.htm", False)):
        out = tmp_path / name
        assert write_report(groups, out) == 3
        assert out.read_bytes().startswith(b"\xef\xbb\xbf") == is_csv
    empty = tmp_path / "bos.html"
    assert write_report([], empty) == 0 and "<html" in empty.read_text(encoding="utf-8")


def test_failed_write_leaves_no_partial_file(tmp_path: Path):
    groups = _groups(tmp_path)
    out = tmp_path / "rapor.html"

    def broken(_path):
        raise RuntimeError("disk dolu")

    with pytest.raises(RuntimeError):
        write_html(groups, out, thumbnail=broken)
    assert list(tmp_path.glob("rapor.html*")) == []
