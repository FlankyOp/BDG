@echo off
REM BDG Prediction Engine - Startup Script for Windows

echo.
echo ========================================
echo   BDG GAME PREDICTION ENGINE
echo   Windows Startup Script
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python found
echo.

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

echo [OK] All dependencies installed
echo.

REM Dashboard mode: launch model API + frontend, open dashboard.html
if "%~1"=="--dashboard" goto dashboard

REM Default: run the CLI prediction engine
echo Starting BDG Prediction Engine...
echo.
python main.py %*
pause
exit /b 0

:dashboard
echo Starting BDG dashboard mode...
echo.

REM Bug-5 fix: run model_api_server from THIS directory (bdg_predictor\)
echo Launching Model API on http://127.0.0.1:8787 ...
start "BDG Model API  [port 8787]" cmd /k python model_api_server.py

echo Launching Frontend   on http://127.0.0.1:8000 ...
start "BDG Frontend    [port 8000]" cmd /k python start_frontend.py

timeout /t 3 >nul

REM Bug-5 fix: open dashboard.html via the frontend server, not as a local file
echo Opening dashboard in browser...
start "" "http://127.0.0.1:8000/dashboard.html"

echo.
echo Dashboard started.
echo - Keep both terminal windows open while using the dashboard.
echo - Close them to stop the servers.
pause
