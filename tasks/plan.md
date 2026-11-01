# Plan: 5. aşama (beta 0.5.0)

Bağımlılık sırası: T1 → T2 ; T3 → T4 ; (T2, T4) → T5 → T6

| # | Görev | Kabul | Doğrulama |
|---|---|---|---|
| T1 | `report.py`: satırlar, CSV (BOM, `;`), HTML (base64 küçük resim, kaçış) | CSV/HTML testleri geçer | `pytest tests/test_report.py` |
| T2 | Rapor düğmesi: kaydetme penceresi, arka planda üretim, durum mesajı | GUI testi: düğme etkin, dosya oluşur | `pytest tests/test_gui.py` |
| T3 | `settings.py`: `AppSettings` yükle/kaydet, eski ayar göçü | INI gidiş-dönüş testi | `pytest tests/test_settings.py` |
| T4 | Ayarlar penceresi + ana pencereye bağlama (eşik, pencere, işçi) | Açılışta varsayılanlar uygulanır; işçi sayısı taramaya gider | `pytest -q` |
| — | **Kontrol noktası**: tüm testler, uygulama elle açılır | | |
| T5 | PyInstaller spec, `requirements-build.txt`, .gitignore | EXE açılır; cli-exe ile HEIC tarama | dist çalıştırma |
| T6 | Sürüm 0.5.0, README, zip | `--version` 0.5.0 | |
