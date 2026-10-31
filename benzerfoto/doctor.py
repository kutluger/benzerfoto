"""Ortam kontrolü: derlenmiş (DLL içeren) paketlerin yüklenip yüklenemediğini gösterir.

Windows 11'in Akıllı Uygulama Denetimi gibi güvenlik özellikleri bazı DLL'leri
engelleyebilir. Bu araç hangi paketin etkilendiğini tek seferde listeler.

Kullanım: python -m benzerfoto.doctor
"""

from __future__ import annotations

import importlib
import platform
import sys

# (gösterilecek ad, içe aktarılacak modül)
CHECKS = [
    ("numpy", "numpy"),
    ("numpy.linalg", "numpy.linalg"),
    ("scipy.fftpack (imagehash)", "scipy.fftpack"),
    ("PyWavelets (imagehash)", "pywt"),
    ("Pillow", "PIL.Image"),
    ("pillow-heif (HEIC)", "pillow_heif"),
    ("ImageHash", "imagehash"),
    ("PySide6 (arayüz)", "PySide6.QtWidgets"),
]


def run_checks() -> list[tuple[str, str | None, str | None]]:
    """Her modül için (ad, sürüm, hata) döndürür; hata None ise sorun yok."""
    results = []
    for label, module in CHECKS:
        try:
            mod = importlib.import_module(module)
            top = sys.modules[module.split(".")[0]]
            version = getattr(top, "__version__", None) or getattr(mod, "__version__", None)
            results.append((label, str(version) if version else "", None))
        except Exception as exc:
            results.append((label, None, f"{type(exc).__name__}: {exc}"))
    return results


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    print(f"Python {platform.python_version()} ({platform.architecture()[0]}) · {platform.platform()}")
    failed = 0
    results = run_checks()
    for label, version, error in results:
        if error is None:
            print(f"  [ OK ] {label} {version}")
        else:
            failed += 1
            print(f"  [HATA] {label}\n         {error}")
    if failed:
        print(f"\n{failed} paket yüklenemedi. Bu ekranın görüntüsünü Claude'a iletebilirsiniz.")
        if any("Denetim" in (e or "") or "Application Control" in (e or "") for _, _, e in results):
            print("Engelleyen: Windows Akıllı Uygulama Denetimi (Smart App Control).")
    else:
        print("\nTüm paketler sorunsuz yüklendi.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
