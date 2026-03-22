@echo off
REM BDG Dashboard Launcher — runs from the root BDG folder
REM Starts the Model API (port 8787) and the Frontend server (port 8000),
REM then opens the dashboard in your default browser.

echo.
echo ========================================
echo   BDG GAME DASHBOARD LAUNCHER
echo ========================================
echo.

REM ─── Check Python ───────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python found

REM ─── Check / install dependencies ──────────────────────────────────────────
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies from bdg_predictor\requirements.txt ...
    pip install -r bdg_predictor\requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
)
echo [OK] Dependencies ready
echo.

REM ─── Start Model API server (port 8787) ─────────────────────────────────────
echo Starting Model API on http://127.0.0.1:8787 ...
start "BDG Model API  [port 8787]" cmd /k "cd /d "%~dp0bdg_predictor" && python model_api_server.py"

REM ─── Start Frontend server (port 8000) ──────────────────────────────────────
echo Starting Frontend  on http://127.0.0.1:8000 ...
start "BDG Frontend    [port 8000]" cmd /k "cd /d "%~dp0bdg_predictor" && python start_frontend.py"

REM ─── Wait for servers to boot ───────────────────────────────────────────────
echo.
echo Waiting for servers to start...
timeout /t 3 >nul

REM ─── Open dashboard ─────────────────────────────────────────────────────────
echo Opening dashboard in browser...
start "" "http://127.0.0.1:8000/dashboard.html"

echo.
echo ========================================
echo   Dashboard is running!
echo   Frontend : http://127.0.0.1:8000/dashboard.html
echo   Model API: http://127.0.0.1:8787/health
echo.
echo   Close the two terminal windows to stop.
echo ========================================
echo.
pause
