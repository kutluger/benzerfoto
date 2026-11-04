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

README = f"""BenzerFoto {__version__}
==============================

Benzer ve kopya fotoğrafları bulup gruplayan, hangisini tutacağınızı
seçmenizi kolaylaştıran program. Kurulum gerekmez.

AÇMAK
  1) Zip dosyasını bir klasöre çıkarın (zip'in içinden çalıştırmayın).
  2) BenzerFoto klasöründeki BenzerFoto.exe dosyasına çift tıklayın.

ZİP'İ E-POSTA, WHATSAPP YA DA İNTERNETTEN ALDIYSANIZ
  Windows indirilen dosyaları daha sıkı denetler ve programı engelleyebilir.
  Zip'i çıkarmadan ÖNCE:
    zip dosyasına sağ tıklayın > Özellikler > en alttaki
    "Engellemeyi kaldır" kutusunu işaretleyin > Tamam.
  Sonra zip'i çıkarın.

"UYGULAMA DENETİMİ İLKESİ BU DOSYAYI ENGELLEDİ" UYARISI ÇIKARSA
  BenzerFoto-ac.bat dosyasına çift tıklayın: aynı program, yanında küçük
  bir konsol penceresiyle açılır. Güvenlik ayarlarını kapatmanız gerekmez.

TAŞINABİLİR
  Ayarlar ve tarama önbelleği programın yanındaki "veri" klasöründe
  tutulur. Klasörü USB belleğe kopyalayıp başka bir bilgisayarda da aynı
  ayarlarla kullanabilirsiniz. Bilgisayara hiçbir şey kurulmaz; programı
  kaldırmak için klasörü silmeniz yeterlidir.
  Programı başkasına verirken "veri" klasörünü vermeyin: içinde sizin
  klasör listeniz ve tarama bilgileriniz var.

GÜVENLİ
  Hiçbir dosya kalıcı silinmez: fazlalıklar _benzerler klasörüne taşınır
  ya da Geri Dönüşüm Kutusu'na gönderilir; her işlem geri alınabilir.
"""


DATA = APP / "veri"  # taşınabilir moddaki kişisel ayarlar ve önbellek
DATA_BACKUP = DIST / "_veri_yedek"


def main() -> int:
    # PyInstaller dist\BenzerFoto klasörünü silip yeniden oluşturur. Program bu
    # klasörden kullanılıyorsa içindeki "veri" klasörü kaybolmasın: kenara al, geri koy.
    if DATA.is_dir():
        shutil.rmtree(DATA_BACKUP, ignore_errors=True)
        shutil.move(DATA, DATA_BACKUP)
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(ROOT / "benzerfoto.spec")], cwd=ROOT, check=True)
    finally:
        if DATA_BACKUP.is_dir():
            APP.mkdir(parents=True, exist_ok=True)
            shutil.move(DATA_BACKUP, DATA)
    shutil.copy2(ROOT / "packaging" / "BenzerFoto-ac.bat", APP / "BenzerFoto-ac.bat")
    (APP / "BENIOKU.txt").write_text(README, encoding="utf-8-sig")
    zip_path = DIST / f"BenzerFoto-{__version__}-win64.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(APP.rglob("*")):
            # Kişisel veriler zip'e girmez
            if f.is_file() and DATA not in f.parents:
                zf.write(f, f.relative_to(DIST))
    print(f"Hazır: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
