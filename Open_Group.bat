@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   CAMOUFOX GMAIL LAUNCHER
echo ========================================
set /p group_name="Enter group name (Example: Group_1): "

REM Validate: only allow alphanumeric, underscore, dash
echo !group_name! | findstr /R "^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$" >nul
if errorlevel 1 (
    echo [!] Invalid group name! Only letters, numbers, underscores, and dashes are allowed.
    pause
    exit /b 1
)

echo.
python run_group.py !group_name!
pause
