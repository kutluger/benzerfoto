"""Uygulama genelindeki sabitler ve varsayılan ayarlar."""

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
    """Önbellek veritabanının konumunu döndürür.

    Paketlenmiş EXE'de program klasöründeki `veri\\benzerfoto.db` (taşınabilir mod),
    kaynaktan çalışırken %LOCALAPPDATA%\\BenzerFoto\\benzerfoto.db. Ayrıntı: paths.py
    """
    from benzerfoto.paths import prepare_location

    return prepare_location().db_path
