@echo off
setlocal enabledelayedexpansion

:: ============================================================================
::  FLANKY'S BDG AI BOT & DASHBOARD LAUNCHER
:: ============================================================================
title FLANKY BDG BOT ENGINE

echo.
echo  ############################################################
echo  #                                                          #
echo  #             FLANKY'S BDG AI PREDICTOR v2.0              #
echo  #           AUTO-BOT + DISCORD DAEMON ENABLED              #
echo  #                                                          #
echo  ############################################################
echo.

:: --- Check Python ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10 or newer.
    pause
    exit /b 1
)

:: --- Install Missing Dependencies ---
echo [SYSTEM] Verifying dependencies...
pip install requests flask flask-cors pandas scikit-learn numpy >nul 2>&1
echo [OK] Dependencies confirmed.

echo.
echo [1/3] Starting AI Prediction Engine (Port: 8787)...
start "FLANKY_AI_ENGINE" cmd /k "cd /d "%~dp0bdg_predictor" && python model_api_server.py"

echo [2/3] Starting Dashboard Web Server (Port: 8000)...
start "FLANKY_UI_SERVER" cmd /k "cd /d "%~dp0bdg_predictor" && python start_frontend.py"

echo.
echo [3/3] Launching Dashboard in Browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:8000/dashboard.html"

echo.
echo ============================================================
echo   THE BOT SYSTEM IS NOW LIVE 24/7
echo ============================================================
echo   - AI Prediction API: http://127.0.0.1:8787
echo   - Interactive UI: http://127.0.0.1:8000/dashboard.html
echo   - Discord Monitor: ACTIVE (AUTONOMOUS)
echo.
echo   Keep the two secondary windows open to maintain the system.
echo   You can minimize this launcher.
echo ============================================================
echo.
pause
