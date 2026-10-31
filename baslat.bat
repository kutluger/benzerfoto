@echo off
rem ============================================================
rem  BenzerFoto - kurulum ve çalıştırma betiği
rem  Çift tıklamanız yeterli. İlk çalıştırmada:
rem    1) Kodu GitHub'dan indirir (gerekirse)
rem    2) Sanal ortamı (.venv) oluşturur
rem    3) Bağımlılıkları kurar
rem    4) Uygulamayı açar
rem  Sonraki çalıştırmalarda güncellemeleri çeker ve doğrudan açar.
rem ============================================================
chcp 65001 >nul
setlocal EnableExtensions

set "REPO_URL=https://github.com/kutluger/benzerfoto"
set "BRANCH=asama-2-gruplama"

rem --- Proje klasörünü bul: betik proje içindeyse orası, değilse kullanıcı klasörü ---
if exist "%~dp0benzerfoto\__init__.py" (
    set "APP_DIR=%~dp0"
) else (
    set "APP_DIR=%USERPROFILE%\benzerfoto"
)

rem --- Git var mı? ---
where git >nul 2>nul
if errorlevel 1 (
    echo [HATA] Git bulunamadı. Kurmak için PowerShell'de şunu çalıştırın:
    echo        winget install --id Git.Git -e
    echo Kurulumdan sonra bu pencereyi kapatıp betiği yeniden çalıştırın.
    pause
    exit /b 1
)

rem --- Python var mı? (py başlatıcısı) ---
where py >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python bulunamadı. Kurmak için PowerShell'de şunu çalıştırın:
    echo        winget install --id Python.Python.3.12 -e
    echo Kurulumdan sonra bu pencereyi kapatıp betiği yeniden çalıştırın.
    pause
    exit /b 1
)

rem --- Kodu indir ya da güncelle ---
if not exist "%APP_DIR%\.git" (
    echo Kod indiriliyor: %APP_DIR%
    git clone "%REPO_URL%" "%APP_DIR%" || goto :error
)
pushd "%APP_DIR%" || goto :error
echo Güncellemeler kontrol ediliyor...
git fetch origin "%BRANCH%" >nul 2>nul
git checkout "%BRANCH%" >nul 2>nul || goto :error
git pull --ff-only origin "%BRANCH%" >nul 2>nul

rem --- Sanal ortam ---
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam oluşturuluyor...
    py -3 -m venv .venv || goto :error
    del ".venv\.requirements-installed" >nul 2>nul
)

rem --- Bağımlılıklar: yalnızca requirements dosyaları değiştiyse yeniden kur ---
fc /b requirements.txt ".venv\.requirements-installed" >nul 2>nul
if errorlevel 1 (
    echo Bağımlılıklar kuruluyor, bu ilk seferde birkaç dakika sürebilir...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt || goto :error
    copy /y requirements.txt ".venv\.requirements-installed" >nul
)

rem --- Uygulamayı aç ---
echo BenzerFoto açılıyor...
".venv\Scripts\python.exe" -m benzerfoto
if errorlevel 1 goto :error
popd
exit /b 0

:error
echo.
echo [HATA] Bir adım başarısız oldu. Yukarıdaki mesajı Claude'a iletebilirsiniz.
pause
exit /b 1
