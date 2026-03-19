@echo off
REM BDG Prediction Engine - Startup Script for Windows
REM This script sets up the environment and runs the prediction engine

echo.
echo ========================================
echo   BDG GAME PREDICTION ENGINE
echo   Windows Startup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://www.python.org/
    pause
    exit /b 1
)

echo ✓ Python found
echo.

REM Check if dependencies are installed
echo Checking dependencies...
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo ✓ All dependencies installed
echo.

REM Dashboard mode: launch model API and open HTML UI
if "%~1"=="--dashboard" goto dashboard

REM Run the main program
echo Starting BDG Prediction Engine...
echo.

python main.py %*

pause
exit /b 0

:dashboard
echo Starting BDG dashboard mode...
echo Launching local model API on http://127.0.0.1:8787
start "BDG Model API" cmd /c python model_api_server.py --host 127.0.0.1 --port 8787

REM Give server a moment to boot before opening UI
timeout /t 2 >nul

echo Opening dashboard in your default browser...
start "" index.html

echo.
echo Dashboard started.
echo - Keep the "BDG Model API" terminal running while using the dashboard.
echo - Close that terminal window to stop model-backed predictions.
pause
