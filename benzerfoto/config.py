"""Uygulama genelindeki sabitler ve varsayılan ayarlar."""

import os
from pathlib import Path

# Taranacak dosya uzantıları (küçük harf). RAW şimdilik kapsam dışı.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
)

# Uygulamanın fazlalıkları taşıyacağı klasörün adı. Tarama sırasında bu
# klasörler her zaman atlanır, yoksa taşınan dosyalar yeniden bulunurdu.
DUPLICATES_FOLDER_NAME = "_benzerler"

# Netlik skoru, farklı çözünürlükteki fotoğrafları adil karşılaştırmak için
# uzun kenarı bu boyuta küçültülmüş görüntü üzerinden hesaplanır.
SHARPNESS_LONG_EDGE = 1024

# Dosya içeriği okunurken kullanılan parça boyutu (bayt)
HASH_CHUNK_SIZE = 1024 * 1024

# Önbelleğe toplu yazma boyutu. İptal edilen bir taramada en fazla bu kadar
# dosyanın işi kaybolur.
DB_BATCH_SIZE = 200


def default_db_path() -> Path:
    """Önbellek veritabanının varsayılan konumunu döndürür.

    Windows'ta %LOCALAPPDATA%\\BenzerFoto\\benzerfoto.db, diğer sistemlerde
    ~/.benzerfoto/benzerfoto.db kullanılır.
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) / "BenzerFoto" if local_app_data else Path.home() / ".benzerfoto"
    return base / "benzerfoto.db"
