@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [1/4] Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
        if errorlevel 1 (
            echo ERROR: Python 3.13+ not found.
            pause
            exit /b 1
        )
    )
)

echo [2/4] Installing runtime dependencies...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install runtime dependencies.
    pause
    exit /b 1
)

echo [3/4] Installing packaging tools...
"%VENV_PY%" -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [4/4] Building release binary...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --windowed --onefile --name DigitalClock --collect-all pynput main.py
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed: dist\DigitalClock.exe
echo You can double-click this file on Windows.
pause
