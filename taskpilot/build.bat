@echo off
REM ============================================================
REM  TaskPilot - build a standalone TaskPilot.exe
REM  Requirements: Python 3.10+ from python.org
REM ============================================================
setlocal

echo.
echo [1/3] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [2/3] Building TaskPilot.exe (this takes a minute)...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name TaskPilot ^
    --clean ^
    main.py
if errorlevel 1 goto :fail

echo.
echo [3/3] Done!
echo   Your app is at:  dist\TaskPilot.exe
echo   Copy that single file anywhere and double-click it.
echo.
pause
exit /b 0

:fail
echo.
echo Build failed - check the messages above.
pause
exit /b 1
