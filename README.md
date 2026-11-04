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
| 4 | Taşıma, geri dönüşüm, işlem günlüğü, geri alma | ✅ |
| 5 | Rapor, ayarlar, EXE paketleme (beta 0.5.0) | ✅ |
| 0.9 | Klavye kısayolları, incelenen gruplara uygulama, grubun tamamını gönderme, BF logosu | ✅ |

Sürüm notları: [CHANGELOG.md](CHANGELOG.md)

## Hazır paket (EXE, Python gerekmez)

`BenzerFoto-<sürüm>-win64.zip` dosyasını bir klasöre açın, **BenzerFoto.exe**'ye çift tıklayın.
Zip'in içindeki **BENIOKU.txt** aynı bilgileri kısaca anlatır.

Zip e-posta, WhatsApp ya da tarayıcıyla indirildiyse Windows ona "internetten geldi"
işareti koyar ve program engellenebilir. Zip'i çıkarmadan önce sağ tıklayın,
**Özellikler**'de en alttaki **Engellemeyi kaldır** kutusunu işaretleyip Tamam'a basın.

**Taşınabilir:** EXE ayarlarını ve tarama önbelleğini kendi yanındaki `veri` klasöründe
tutar, bilgisayara bir şey yazmaz. Klasör USB belleğe kopyalanıp başka bilgisayarda aynı
ayarlarla kullanılabilir. İlk açılışta, varsa eski konumdaki (`%LOCALAPPDATA%\BenzerFoto`
ve kayıt defteri) ayarlar ve önbellek bir kez `veri` klasörüne kopyalanır. Program klasörü
yazılamıyorsa (ör. Program Files) eski konum kullanılır. Programı başkasına verirken
`veri` klasörünü vermeyin; `paketle.py` onu zip'e koymaz. Python ile kaynaktan
çalıştırınca (`baslat.bat`) veriler eskisi gibi `%LOCALAPPDATA%\BenzerFoto`'da kalır.

Windows 11'in **Akıllı Uygulama Denetimi** imzasız programları engelleyebilir
(“Uygulama Denetimi ilkesi bu dosyayı engelledi”). Bu durumda güvenlik ayarını
değiştirmeyin; aynı klasördeki **BenzerFoto-ac.bat** dosyasını çalıştırın (aynı program,
konsol penceresiyle açılır) ya da aşağıdaki `baslat.bat` yolunu kullanın.

## Kolay kurulum (Windows)

`baslat.bat` dosyasını indirip çift tıklayın. Git ya da yönetici izni gerekmez.
Python yoksa kullanıcı hesabına kurar, kodun son halini zip olarak
`%USERPROFILE%\benzerfoto` klasörüne indirir, sanal ortamı ve bağımlılıkları kurar,
uygulamayı açar. Her çalıştırmada son sürümü indirir; bağımlılıkları yalnızca
değiştiyse yeniden kurar.

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
   Sağ tıktaki **Dosya konumunu aç**, klasörü fotoğraf seçili olarak açar.
5. Fare tekerleği önizlemeyi yakınlaştırır, çift tık pencereye sığdırır.
   Klavye kısayolları (tam liste için **F1**):

   | Tuş | İşlev |
   |---|---|
   | Enter | Grubu incelendi olarak işaretle ve sonraki gruba geç |
   | Page Down / Page Up | Sonraki / önceki grup (Ctrl+→ / Ctrl+← de çalışır) |
   | → / ← | Gruptaki sonraki / önceki fotoğraf |
   | Boşluk | Seçili fotoğrafın işaretini aç / kapat |
   | Delete | Seçili fotoğrafı onay sorarak Geri Dönüşüm Kutusu'na gönder (geri alınabilir) |
   | F1 | Kısayol listesi |

   Kısayollar hangi panel seçili olursa olsun çalışır; arama kutusuna yazarken devre dışıdır.

   **İnceleme:** bir grubun seçimini değiştirdiğinizde ya da Sonraki / Page Down ile
   geçtiğinizde grup **✓ İncelendi** olur (sağ üstteki düğmeyle elle de açılıp kapanır).
   Listede yeşil şeritle görünür; **İncelenmemiş / İncelendi** filtreleri kaç grup kaldığını
   gösterir. İnceleme durumu ve işaretler önbellek veritabanında dosya bazında saklanır:
   uygulamayı kapatıp ertesi gün yeniden tarasanız da kaldığınız yerden devam edersiniz.
6. Alttaki **📦 _benzerler klasörüne taşı** ya da **🗑 Geri Dönüşüm Kutusu'na gönder** ile işaretli
   dosyaları ayırın. Önce **tüm gruplar**, **incelenen gruplar** (örneğin 250 gruptan
   baktığınız ilk 50'si) ya da **yalnızca bu grup** seçilir.
   - Taşıma: dosya, bulunduğu tarama klasörünün içindeki `_benzerler` klasörüne alt klasör
     yapısı korunarak taşınır (`D:\Foto\2020\a.jpg` → `D:\Foto\_benzerler\2020\a.jpg`).
     Aynı adlı dosya varsa üzerine yazılmaz, `a (2).jpg` olarak taşınır.
   - Geri Dönüşüm Kutusu yalnızca sabit yerel sürücülerde kullanılır; ağ ve USB sürücülerinde
     Windows dosyayı kalıcı sileceği için işlem yapılmaz. Kutuya sığmayan bir dosya olursa
     Windows ayrıca sorar.
   - Tüm fotoğrafları işaretli gruplar atlanır, korunan klasördeki dosyalar hiçbir zaman işlenmez.
   - Bir grubun hiçbir fotoğrafını tutmak istemiyorsanız sağ üstteki **⋯** menüsünden (ya da
     sağ tıkla) **Grubun tamamını Geri Dönüşüm Kutusu'na gönder** seçin. İki ayrı onay istenir;
     ikincisinde kutuyu işaretlemeden düğme açılmaz. Bu işlem de geri alınabilir.
7. **📄 Rapor** seçili moddaki tüm grupları kaydeder (sıralama ekrandakiyle aynı):
   - **HTML**: küçük resimler dosyanın içine gömülüdür; tek dosyadır, internetsiz açılır.
   - **CSV**: Excel'de Türkçe karakterler ve sütunlar doğru açılır (UTF-8 BOM, `;` ayırıcı).
   Sütunlar: tür, grup no, durum (★ Önerilen / İşaretli / Korunan / Tutulacak), yol, boyut,
   çözünürlük, çekim zamanı, netlik.
8. **⚙ Ayarlar**: benzer ve aynı sahne eşikleri, aynı sahne zaman penceresi ve tarama işçi
   sayısı (0 = otomatik). Eşikler ve zaman penceresi her açılışta buradaki değerlerle başlar;
   kaydırıcı yalnızca o oturumu etkiler. **Fabrika değerleri** düğmesi varsayılanlara döndürür.
9. **↶ Geri Al** son işlemi geri alır: dosyalar özgün yerlerine döner (kutuya gönderilenler de,
   kutu boşaltılmadıysa). Özgün yerde aynı adlı dosya varsa o dosya atlanır, geri alma daha
   sonra tekrar denenebilir. **🕘 Geçmiş** penceresi tüm işlemleri dosya dosya listeler ve
   istenen işlemi geri almayı sağlar. Günlük, önbellekle aynı veritabanında tutulur.

### Eşikler

| Mod | Varsayılan | Anlamı |
|---|---|---|
| Benzer görüntü | %80 (13 bit) | Farklı boyut/format, hafif düzenleme. Denemelerde en kararlı değer: %60'ta alakasız fotoğraflar eşleşiyor, %80'in üstünde çok benzeyenler kaçıyor |
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

- `--settings-file ayarlar.ini` ayarları kayıt defteri yerine bir dosyada tutar (taşınabilir kullanım).
- `python -m benzerfoto doctor` gerekli paketlerin yüklenip yüklenemediğini gösterir.

Desteklenen formatlar: JPG, PNG, WEBP, HEIC/HEIF.

## Testler

```powershell
python -m pytest
```

Testler yalnızca geçici klasörlerde üretilen görsellerle ve geçici ayar dosyasıyla çalışır.

## EXE paketleme

```powershell
pip install -r requirements-build.txt
python packaging\paketle.py
```

`benzerfoto.spec` (PyInstaller, `--onedir`) iki program üretir: `BenzerFoto.exe` (arayüz) ve
`benzerfoto-cli.exe` (komut satırı). HEIC kütüphanesi (libheif) ve Qt eklentileri pakete dahildir.
Çıktı: `dist\BenzerFoto\` ve `dist\BenzerFoto-<sürüm>-win64.zip`.

## Proje yapısı

```
benzerfoto/
  config.py     sabitler, önbellek konumu
  paths.py      veri klasörü: taşınabilir mod (EXE yanında veri\) ya da %LOCALAPPDATA%
  discovery.py  klasörlerde gezinme, hariç tutma
  features.py   bir fotoğraftan hash, pHash/dHash, EXIF, netlik çıkarma
  cache.py      SQLite önbellek
  scanner.py    tarama motoru (çok çekirdekli, ilerleme, iptal)
  grouping.py   kopya / benzer / aynı sahne gruplama, en iyiyi önerme
  actions.py    _benzerler'e taşıma, Geri Dönüşüm Kutusu, geri alma
  journal.py    işlem günlüğü (SQLite)
  recycle.py    Windows Geri Dönüşüm Kutusu'na gönderme ve geri yükleme
  formatting.py Türkçe boyut ve tarih biçimleri
  report.py     CSV ve tek dosyalı HTML rapor
  settings.py   kalıcı ayarlar (varsayılan eşikler, zaman penceresi, işçi sayısı)
  review.py     inceleme durumu ve işaretlerin kalıcı kaydı (SQLite)
  assets/       BF logosu (SVG kaynağı, PNG'ler, bf.ico)
  cli.py        komut satırı aracı
  gui/          PySide6 arayüzü (ana pencere, bileşenler, stil, arka plan işleri)
tests/          pytest testleri
packaging/      EXE paketi ve zip hazırlama, logo_uret.py (SVG → PNG/ICO)
```
