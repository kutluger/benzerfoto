@echo off
rem ============================================================
rem  BenzerFoto - kurulum ve çalıştırma betiği
rem  Çift tıklamanız yeterli; Git ya da yönetici izni gerekmez.
rem    1) Python yoksa kullanıcı hesabına kurar
rem    2) Kodun son halini GitHub'dan zip olarak indirir
rem    3) Sanal ortamı (.venv) ve bağımlılıkları kurar
rem    4) Uygulamayı açar
rem ============================================================
chcp 65001 >nul
setlocal EnableExtensions

set "BRANCH=asama-2-gruplama"
set "ZIP_URL=https://github.com/kutluger/benzerfoto/archive/refs/heads/%BRANCH%.zip"
set "PY_VERSION=3.12.7"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"
set "APP_DIR=%USERPROFILE%\benzerfoto"
set "WORK=%TEMP%\benzerfoto-kurulum"

rem --- 1) Python'u bul ---
call :find_python
if not defined PYTHON (
    echo Python bulunamadı, kuruluyor. Bu birkaç dakika sürebilir...
    if not exist "%WORK%" mkdir "%WORK%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%PY_URL%' -OutFile '%WORK%\python-setup.exe'" || goto :error
    rem Sessiz kurulum: yalnızca bu kullanıcıya, PATH'e ekle, py başlatıcısıyla birlikte
    "%WORK%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 || goto :error
    call :find_python
)
if not defined PYTHON (
    echo [HATA] Python kurulamadı. https://www.python.org/downloads/ adresinden elle kurup
    echo        kurulumda "Add python.exe to PATH" kutusunu işaretleyin.
    goto :error
)
echo Python: %PYTHON%

rem --- 2) Kodun son halini indir (internet yoksa mevcut kopyayla devam et) ---
echo Kodun son hali indiriliyor...
if exist "%WORK%\kod" rmdir /s /q "%WORK%\kod"
mkdir "%WORK%\kod" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%ZIP_URL%' -OutFile '%WORK%\kod.zip'; Expand-Archive -Force '%WORK%\kod.zip' '%WORK%\kod'"
if errorlevel 1 (
    if exist "%APP_DIR%\benzerfoto\__init__.py" (
        echo [UYARI] İndirilemedi, bilgisayardaki mevcut sürüm açılacak.
    ) else (
        echo [HATA] Kod indirilemedi. İnternet bağlantınızı kontrol edin.
        goto :error
    )
) else (
    rem Zip içindeki klasörü proje klasörüne kopyala; .venv korunur
    for /d %%D in ("%WORK%\kod\*") do robocopy "%%D" "%APP_DIR%" /E /NFL /NDL /NJH /NJS /NP /XD .venv >nul
)

pushd "%APP_DIR%" || goto :error

rem --- 3) Sanal ortam ve bağımlılıklar ---
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam oluşturuluyor...
    "%PYTHON%" -m venv .venv || goto :error
    del ".venv\.requirements-installed" >nul 2>nul
)
rem requirements.txt değişmediyse kurulum atlanır
fc /b requirements.txt ".venv\.requirements-installed" >nul 2>nul
if errorlevel 1 (
    echo Bağımlılıklar kuruluyor, ilk seferde birkaç dakika sürebilir...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install --upgrade -r requirements-dev.txt || goto :error
    copy /y requirements.txt ".venv\.requirements-installed" >nul
)

rem --- 4) Paketler yüklenebiliyor mu? (Windows güvenlik engellerini yakalar) ---
".venv\Scripts\python.exe" -m benzerfoto.doctor
if errorlevel 1 goto :error

rem --- 5) Uygulamayı aç ---
echo BenzerFoto açılıyor...
".venv\Scripts\python.exe" -m benzerfoto
if errorlevel 1 goto :error
popd
exit /b 0

rem ------------------------------------------------------------
:find_python
rem Önce py başlatıcısı, sonra kullanıcı kurulumu, sonra PATH'teki python.
rem (Windows'un Microsoft Store kısayolu gerçek Python değildir, -c testiyle elenir.)
set "PYTHON="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%P"
if defined PYTHON exit /b 0
for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%P\python.exe" set "PYTHON=%%P\python.exe"
)
if defined PYTHON exit /b 0
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%P"
exit /b 0

:error
echo.
echo [HATA] Bir adım başarısız oldu. Yukarıdaki mesajı Claude'a iletebilirsiniz.
pause
exit /b 1
