@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [1/3] Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo py launcher not available, trying python...
        python -m venv .venv
        if errorlevel 1 (
            echo ERROR: Python 3.13+ not found.
            echo Please install Python and try again.
            pause
            exit /b 1
        )
    )
)

echo [2/3] Installing dependencies...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/3] Launching Digital Clock...
"%VENV_PY%" main.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo Digital Clock exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
