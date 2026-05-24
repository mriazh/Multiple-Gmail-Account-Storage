@echo off
cd /d "%~dp0"

REM Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Run the main menu
python main_menu.py
if errorlevel 1 (
    echo.
    echo An error occurred. Check logs/ for details.
    pause
)
