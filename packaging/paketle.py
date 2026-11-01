"""EXE paketini derler ve kullanıcıya verilecek zip dosyasını hazırlar.

Kullanım (proje klasöründe):
    .venv\\Scripts\\python -m pip install -r requirements-build.txt
    .venv\\Scripts\\python packaging\\paketle.py

Çıktı: dist\\BenzerFoto\\ (çalışan klasör) ve dist\\BenzerFoto-<sürüm>-win64.zip
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benzerfoto import __version__  # noqa: E402

DIST = ROOT / "dist"
APP = DIST / "BenzerFoto"

README = f"""BenzerFoto {__version__} (beta)
==============================

Açmak için BenzerFoto.exe dosyasına çift tıklayın.

Windows "Akıllı Uygulama Denetimi" imzasız programları engelleyebilir.
"Uygulama Denetimi ilkesi bu dosyayı engelledi" uyarısı alırsanız:
  1) BenzerFoto-ac.bat dosyasına çift tıklayın (aynı program, konsol penceresiyle açılır), ya da
  2) GitHub'daki baslat.bat ile Python sürümünü kullanın.
Güvenlik ayarlarını değiştirmeniz gerekmez.

Hiçbir dosya kalıcı silinmez: fazlalıklar _benzerler klasörüne taşınır ya da
Geri Dönüşüm Kutusu'na gönderilir; her işlem geri alınabilir.
"""


def main() -> int:
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(ROOT / "benzerfoto.spec")], cwd=ROOT, check=True)
    shutil.copy2(ROOT / "packaging" / "BenzerFoto-ac.bat", APP / "BenzerFoto-ac.bat")
    (APP / "BENIOKU.txt").write_text(README, encoding="utf-8-sig")
    zip_path = DIST / f"BenzerFoto-{__version__}-win64.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(APP.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(DIST))
    print(f"Hazır: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
