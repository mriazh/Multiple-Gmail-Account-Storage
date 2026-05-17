@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   CAMOUFOX GMAIL LAUNCHER
echo ========================================
set /p nama_grup="Masukkan nama grup (Contoh: Grup_1): "

REM Validate: hanya allow alphanumeric, underscore, dash
echo !nama_grup! | findstr /R "^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$" >nul
if errorlevel 1 (
    echo [!] Nama grup tidak valid! Hanya boleh huruf, angka, underscore, dan dash.
    pause
    exit /b 1
)

echo.
python jalankan_grup.py !nama_grup!
pause
