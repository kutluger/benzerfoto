"""Komut satırı: sürüm, taşınabilir ayar dosyası seçeneği ve ortam kontrolü."""

from __future__ import annotations

from pathlib import Path

import pytest

from benzerfoto import __version__
from benzerfoto.cli import build_parser, main


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "1.0.0" in capsys.readouterr().out
    assert __version__ == "1.0.0"


def test_settings_file_option(tmp_path: Path):
    args = build_parser().parse_args(["--settings-file", str(tmp_path / "a.ini"), "gui"])
    assert args.settings_file == tmp_path / "a.ini"
    assert build_parser().parse_args([]).settings_file is None


def test_doctor_command(capsys):
    assert main(["doctor"]) == 0
    assert "Tüm paketler sorunsuz yüklendi" in capsys.readouterr().out
