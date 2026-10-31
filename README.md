# BenzerFoto

Fotoğraf arşivindeki **birebir kopyaları**, **benzer fotoğrafları** ve elle tekrar
tekrar çekilmiş **aynı sahne** karelerini bulup gruplayan Windows masaüstü uygulaması.
Hiçbir dosya kalıcı olarak silinmez; fazlalıklar `_benzerler` klasörüne taşınır ya da
Geri Dönüşüm Kutusu'na gönderilir, her işlem geri alınabilir.

## Geliştirme aşamaları

| Aşama | İçerik | Durum |
|---|---|---|
| 1 | Tarama motoru + SQLite önbellek (komut satırı) | ✅ |
| 2 | Gruplama: kopya / benzer / aynı sahne, en iyiyi önerme | ⏳ |
| 3 | PySide6 arayüzü | ⏳ |
| 4 | Taşıma, geri dönüşüm, işlem günlüğü, geri alma | ⏳ |
| 5 | Rapor, ayarlar, EXE paketleme | ⏳ |

## Kurulum (Windows)

Python 3.11 veya üstü gerekir.

```powershell
git clone https://github.com/kutluger/benzerfoto
cd benzerfoto
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Komut satırından kullanım (1. aşama)

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
  cli.py        komut satırı aracı
tests/          pytest testleri
```
