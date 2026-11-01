@echo off
rem BenzerFoto.exe Windows Akilli Uygulama Denetimi tarafindan engellenirse
rem arayuzu bu dosyayla acabilirsiniz (ayni program, konsol penceresiyle acilir).
"%SystemRoot%\System32\chcp.com" 65001 >nul
"%~dp0benzerfoto-cli.exe" gui
if errorlevel 1 pause
