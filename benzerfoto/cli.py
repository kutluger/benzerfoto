"""Komut satırı aracı. 1. aşamada tarama motorunu arayüz olmadan test etmek için.

Örnekler:
    python -m benzerfoto scan "D:\\Fotoğraflar" --exclude "D:\\Fotoğraflar\\Albümler"
    python -m benzerfoto info
    python -m benzerfoto            (görsel arayüz)
"""

from __future__ import annotations

import argparse
import sys
import threading
from collections import Counter
from pathlib import Path

from benzerfoto import __version__
from benzerfoto.cache import FeatureCache
from benzerfoto.config import default_db_path
from benzerfoto.formatting import format_size
from benzerfoto.scanner import ScanProgress, default_workers, scan


def _print_progress(p: ScanProgress) -> None:
    """İlerlemeyi tek satırda günceller."""
    if p.phase == "discover":
        sys.stderr.write(f"\rDosyalar aranıyor... {p.done} bulundu")
    elif p.phase == "process" and p.total:
        width = 30
        filled = int(width * p.done / p.total)
        bar = "#" * filled + "-" * (width - filled)
        sys.stderr.write(f"\rİşleniyor [{bar}] {p.done}/{p.total} (%{100 * p.done // p.total})  ")
    elif p.phase == "done":
        sys.stderr.write("\n")
    sys.stderr.flush()


def cmd_scan(args: argparse.Namespace) -> int:
    for root in args.roots:
        if not Path(root).is_dir():
            print(f"Hata: klasör bulunamadı: {root}", file=sys.stderr)
            return 2

    cancel_event = threading.Event()
    with FeatureCache(args.db) as cache:
        outcome: dict = {}

        def run() -> None:
            try:
                outcome["result"] = scan(
                    args.roots,
                    cache,
                    excludes=args.exclude,
                    recursive=not args.no_recursive,
                    workers=args.workers,
                    progress=_print_progress,
                    cancel_event=cancel_event,
                )
            except BaseException as exc:  # hatayı ana iş parçacığına taşı
                outcome["error"] = exc

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            while worker.is_alive():
                worker.join(0.2)
        except KeyboardInterrupt:
            # Ctrl+C: tarama düzgünce durdurulur, işlenenler önbellekte kalır
            print("\nİptal ediliyor, çalışan işler bitiriliyor...", file=sys.stderr)
            cancel_event.set()
            worker.join()
        if "error" in outcome:
            raise outcome["error"]
        result = outcome["result"]

        print()
        print(f"Toplam dosya      : {result.total_files} ({format_size(result.total_bytes)})")
        print(f"Önbellekten       : {result.from_cache}")
        print(f"Yeni işlenen      : {result.processed}")
        print(f"Okunamayan        : {result.failed}")
        print(f"Önbellekten silinen (diskte yok): {result.removed}")
        print(f"Süre              : {result.elapsed:.1f} sn")
        if result.cancelled:
            print("Not: tarama iptal edildi, kalan dosyalar bir sonraki taramada işlenecek.")

        failed = [f for f in result.features if not f.ok]
        if failed and args.verbose:
            print("\nOkunamayan dosyalar:")
            for f in failed:
                print(f"  {f.path}\n    {f.error}")

        # Hızlı bir ön bakış: aynı içerik hash'ine sahip dosyalar (asıl gruplama 2. aşamada)
        hashes = Counter(f.content_hash for f in result.features if f.content_hash)
        dup_groups = sum(1 for c in hashes.values() if c > 1)
        dup_files = sum(c - 1 for c in hashes.values() if c > 1)
        print(f"\nÖn bakış: {dup_groups} grupta {dup_files} birebir kopya dosya var.")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    if not Path(args.db).exists():
        print(f"Önbellek henüz oluşturulmamış: {args.db}")
        return 0
    with FeatureCache(args.db) as cache:
        features = cache.get_features()
        print(f"Önbellek: {args.db}")
        print(f"Kayıt sayısı : {len(features)}")
        print(f"Okunamayan   : {sum(1 for f in features if not f.ok)}")
        print(f"EXIF zamanı olan: {sum(1 for f in features if f.taken_at)}")
        exts = Counter(Path(f.path).suffix.lower() for f in features)
        print("Formatlar    : " + ", ".join(f"{ext} {n}" for ext, n in exts.most_common()))
        cameras = Counter(f.camera for f in features if f.camera)
        if cameras:
            print("Cihazlar     : " + ", ".join(f"{c} {n}" for c, n in cameras.most_common(5)))
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    # PySide6 yalnızca arayüz açılırken yüklenir; komut satırı onsuz da çalışır
    from benzerfoto.gui.app import run

    return run(args.db, args.settings_file)


def cmd_doctor(_args: argparse.Namespace) -> int:
    from benzerfoto.doctor import main as doctor_main

    return doctor_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benzerfoto", description="Benzer ve kopya fotoğraf bulucu (komut satırı)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--db", type=Path, default=default_db_path(), help="önbellek veritabanı yolu"
    )
    parser.add_argument(
        "--settings-file",
        type=Path,
        default=None,
        help="ayarları kayıt defteri yerine bu INI dosyasında tut (yalnızca arayüz için; taşınabilir kullanım)",
    )
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="klasörleri tara ve önbelleği güncelle")
    p_scan.add_argument("roots", nargs="+", help="taranacak klasörler")
    p_scan.add_argument("-x", "--exclude", action="append", default=[], help="hariç tutulacak klasör (birden fazla verilebilir)")
    p_scan.add_argument("--no-recursive", action="store_true", help="alt klasörlere inme")
    p_scan.add_argument("-w", "--workers", type=int, default=default_workers(), help="paralel süreç sayısı")
    p_scan.add_argument("-v", "--verbose", action="store_true", help="okunamayan dosyaları listele")
    p_scan.set_defaults(func=cmd_scan)

    p_info = sub.add_parser("info", help="önbellek özetini göster")
    p_info.set_defaults(func=cmd_info)

    p_gui = sub.add_parser("gui", help="görsel arayüzü aç (varsayılan)")
    p_gui.set_defaults(func=cmd_gui)

    p_doctor = sub.add_parser("doctor", help="gerekli paketlerin yüklenebildiğini kontrol et")
    p_doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows konsolunda Türkçe karakterlerin düzgün görünmesi için
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if args.command is None:
        # Komut verilmezse arayüz açılır: python -m benzerfoto
        return cmd_gui(args)
    return args.func(args)
