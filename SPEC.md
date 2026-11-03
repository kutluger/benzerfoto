# Spec: BenzerFoto 5. aşama — beta 0.5.0

## Amaç
İlk beta sürümü: kullanıcı bulduğu grupları rapor olarak dışa aktarabilsin, temel
ayarları kalıcı olarak değiştirebilsin ve uygulamayı Python kurmadan bir EXE
klasöründen açabilsin. Kullanıcı: kendi fotoğraf arşivini temizleyen, teknik
olmayan Windows kullanıcısı.

## Varsayımlar
1. Rapor, **seçili moddaki tüm grupları** (filtre uygulanmadan, seçili sıralamayla)
   içerir; grup no arayüzdeki “Grup #” ile aynı sıradır (filtre yokken).
2. CSV ayırıcısı `;` (Türkçe Excel ondalık virgül kullanır), kodlama UTF-8 BOM.
3. Ayarlar penceresindeki eşikler ve zaman penceresi **açılış varsayılanlarıdır**:
   uygulama her açılışta bunlarla başlar, kaydırıcı oturum içi ayardır. Pencerede
   “Tamam” denince değerler hemen de uygulanır.
4. İşçi sayısı 0 = otomatik (çekirdek sayısı − 1).
5. `_benzerler` klasör adı değiştirilemez; pencerede yalnızca bilgi olarak görünür.
6. EXE: PyInstaller `--onedir`; iki giriş: `BenzerFoto.exe` (pencereli) ve
   `benzerfoto-cli.exe` (konsol: tarama, doctor). Aynı klasördeki kütüphaneleri paylaşır.

## Kabul ölçütleri
- **Rapor**: “📄 Rapor” grup varken etkin. Kaydetme penceresi `.html`/`.csv` sunar.
  - CSV sütunları: Tür, Grup No, Durum, Yol, Boyut (bayt), Boyut, Çözünürlük,
    Çekim zamanı, Netlik. Durum: “★ Önerilen”, “İşaretli”, “Korunan”, “Tutulacak”.
    Dosya `EF BB BF` ile başlar.
  - HTML: tek dosya, dış bağlantı/betik yok, küçük resimler `data:image/jpeg;base64`.
    Yollar HTML kaçışlı. Okunamayan görsel raporu bozmaz (yer tutucu).
  - Arka planda üretilir, arayüz donmaz.
- **Ayarlar**: “⚙ Ayarlar” penceresi; benzer %, sahne %, zaman penceresi, işçi sayısı,
  fabrika değerlerine dönme. QSettings'te kalıcı. Testler yalnızca geçici INI
  dosyasına yazar (gerçek kayıt defterine asla dokunmaz).
- **EXE**: `benzerfoto.spec` repoda; `dist/`, `build/` yok sayılır. Paket açılır,
  HEIC okunur, çok çekirdekli tarama çalışır. `dist/BenzerFoto-0.5.0-win64.zip` üretilir.
- Sürüm 0.5.0, README güncel, `baslat.bat` çalışmaya devam eder.

## Komutlar
```
Test : .venv\Scripts\python -m pytest -q
Çalıştır: .venv\Scripts\python -m benzerfoto
EXE  : .venv\Scripts\python -m PyInstaller --noconfirm benzerfoto.spec
```

## Proje yapısı
- `benzerfoto/report.py` — rapor satırları, CSV ve HTML yazımı (Qt'siz, test edilebilir)
- `benzerfoto/settings.py` — `AppSettings` (yükle/kaydet, QSettings nesnesi dışarıdan verilir)
- `benzerfoto/gui/settings_dialog.py` — Ayarlar penceresi
- `benzerfoto.spec`, `requirements-build.txt` — paketleme
- `tests/test_report.py`, `tests/test_settings.py`

## Kod stili
Kod içi adlar İngilizce, yorumlar ve arayüz metinleri Türkçe; mevcut modüllerdeki
gibi kısa docstring, `from __future__ import annotations`.

## Test stratejisi
pytest; görseller `tmp_path` içinde üretilir (conftest `make_scene`). Rapor saf
fonksiyonlarla birim testi, ayarlar INI dosyasıyla gidiş-dönüş testi, GUI duman testi.

## Sınırlar
- Her zaman: tüm testler geçmeden commit yok; kullanıcı fotoğraflarına dokunma.
- Önce sor: yeni çalışma bağımlılığı (PyInstaller yalnızca derleme bağımlılığı).
- Asla: kalıcı silme, güvenlik ayarı (Akıllı Uygulama Denetimi/Defender) değiştirme,
  `.claude/`, `CLAUDE.md`, `graphify-out/` commit'i.
