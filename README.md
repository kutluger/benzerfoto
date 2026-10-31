# BenzerFoto

Fotoğraf arşivindeki **birebir kopyaları**, **benzer fotoğrafları** ve elle tekrar
tekrar çekilmiş **aynı sahne** karelerini bulup gruplayan Windows masaüstü uygulaması.
Hiçbir dosya kalıcı olarak silinmez; fazlalıklar `_benzerler` klasörüne taşınır ya da
Geri Dönüşüm Kutusu'na gönderilir, her işlem geri alınabilir.

## Geliştirme aşamaları

| Aşama | İçerik | Durum |
|---|---|---|
| 1 | Tarama motoru + SQLite önbellek (komut satırı) | ✅ |
| 2 | Gruplama: kopya / benzer / aynı sahne, en iyiyi önerme | ✅ |
| 3 | PySide6 arayüzü | ✅ |
| 4 | Taşıma, geri dönüşüm, işlem günlüğü, geri alma | ⏳ |
| 5 | Rapor, ayarlar, EXE paketleme | ⏳ |

## Kolay kurulum (Windows)

`baslat.bat` dosyasını indirip çift tıklayın. Betik kodu `%USERPROFILE%\benzerfoto`
klasörüne indirir, sanal ortamı ve bağımlılıkları kurar, uygulamayı açar. Sonraki
çalıştırmalarda güncellemeleri çeker ve doğrudan açar. Git ve Python (`py`) kurulu
olmalıdır; yoksa betik nasıl kurulacağını söyler.

## Elle kurulum (Windows)

Python 3.11 veya üstü gerekir.

```powershell
git clone https://github.com/kutluger/benzerfoto
cd benzerfoto
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Uygulamayı açma

```powershell
python -m benzerfoto
```

1. **+ Ekle** ile taranacak klasörleri seçin. **Hariç tut** taranmayacak alt klasörü,
   **Koru** ise içindeki fotoğrafların asla işaretlenmeyeceği klasörü ekler.
2. Bulma modunu seçin, **TARA**'ya basın. Mod düğmelerinde her modun grup sayısı görünür.
3. Eşik kaydırıcısı ve zaman penceresi değiştikçe gruplar yeniden tarama yapmadan
   hesaplanır.
4. Ortadaki listeden bir grup seçin. ★ önerilen kare korunur, diğerleri kırmızı işaretle
   "ayrılacak" olarak gelir. Kartın kutusuna tıklayarak (ya da Boşluk tuşuyla) işareti
   değiştirebilir, sağ tıklayıp **Bunu tut** ile öneriyi değiştirebilirsiniz.
5. Fare tekerleği önizlemeyi yakınlaştırır, çift tık pencereye sığdırır.
   Gruplar arasında **Ctrl+←/→** ile gezinilir.

Taşıma / Geri Dönüşüm / Geri Al düğmeleri 4. aşamada çalışır hale gelecek.

### Eşikler

| Mod | Varsayılan | Anlamı |
|---|---|---|
| Benzer görüntü | %88 (8 bit) | Farklı boyut/format, hafif düzenleme |
| Aynı sahne | %72 (18 bit) + 60 sn | Elle tekrar çekim, kıpırdanma ve küçük kadraj farkı |

Yüzde arttıkça eşleşme katılaşır. Aynı sahne modunda iki karenin EXIF çekim zamanları
arasında en fazla seçilen süre kadar fark olmalıdır.

## Komut satırından kullanım

```powershell
# Bir ya da birden fazla klasörü tara (alt klasörler dahil)
python -m benzerfoto scan "D:\Fotoğraflar" "E:\Telefon Aktarım"

# Bir klasörü hariç tut (-x birden fazla kez verilebilir)
python -m benzerfoto scan "D:\Fotoğraflar" -x "D:\Fotoğraflar\Albümler"

# Okunamayan dosyaları da listele
python -m benzerfoto scan "D:\Fotoğraflar" -v

# Önbellek özeti (kayıt sayısı, formatlar, cihazlar)
python -m benzerfoto info
```

- İlk tarama her dosyayı okur. Sonraki taramalarda yalnızca **yeni ya da değişmiş**
  dosyalar işlenir (yol, boyut ve değiştirilme zamanı karşılaştırılır).
- Tarama `Ctrl+C` ile iptal edilebilir. O ana kadar işlenenler kaybolmaz, bir sonraki
  tarama kaldığı yerden devam eder.
- Önbellek varsayılan olarak `%LOCALAPPDATA%\BenzerFoto\benzerfoto.db` dosyasındadır.
  Farklı bir konum için `--db yol\dosya.db` kullanılabilir (komuttan önce yazılır).
- `_benzerler` adlı klasörler her zaman atlanır.

Desteklenen formatlar: JPG, PNG, WEBP, HEIC/HEIF.

## Testler

```powershell
python -m pytest
```

## Proje yapısı

```
benzerfoto/
  config.py     sabitler, varsayılan önbellek konumu
  discovery.py  klasörlerde gezinme, hariç tutma
  features.py   bir fotoğraftan hash, pHash/dHash, EXIF, netlik çıkarma
  cache.py      SQLite önbellek
  scanner.py    tarama motoru (çok çekirdekli, ilerleme, iptal)
  grouping.py   kopya / benzer / aynı sahne gruplama, en iyiyi önerme
  formatting.py Türkçe boyut ve tarih biçimleri
  cli.py        komut satırı aracı
  gui/          PySide6 arayüzü (ana pencere, bileşenler, stil, arka plan işleri)
tests/          pytest testleri
```
