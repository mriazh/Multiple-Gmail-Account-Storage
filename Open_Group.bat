@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   CAMOUFOX GMAIL LAUNCHER
echo ========================================
echo.
echo Available groups:
echo ----------------------------------------

set count=0
for /d %%D in (*) do (
    set "folder=%%D"
    REM Skip hidden/system folders
    if /i not "!folder!"==".git" (
        if /i not "!folder!"=="logs" (
            if /i not "!folder!"=="__pycache__" (
                set /a count+=1
                set "group_!count!=%%D"
                echo   !count!. %%D
            )
        )
    )
)

if !count!==0 (
    echo   [No groups found]
    echo.
    echo   Create a group folder first, e.g. "Group_1"
    pause
    exit /b 1
)

echo ----------------------------------------
echo.
echo You can enter:
echo   - A number (e.g. 1)
echo   - A group name (e.g. Group_1)
echo.
set /p "input=Select group: "

REM Check if input is a number
set "is_number=1"
for /f "delims=0123456789" %%i in ("!input!") do set "is_number=0"

if "!is_number!"=="1" (
    if !input! GEQ 1 if !input! LEQ !count! (
        set "group_name=!group_!input!!"
        goto :run
    )
    echo [!] Invalid number. Please pick between 1 and !count!.
    pause
    exit /b 1
)

REM Input is a name — validate characters
echo !input! | findstr /R "^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$" >nul
if errorlevel 1 (
    echo [!] Invalid group name! Only letters, numbers, underscores, and dashes allowed.
    pause
    exit /b 1
)

set "group_name=!input!"

:run
echo.
python run_group.py !group_name!
pause
