@echo off
REM ============================================================================
REM BDG Predictor - One-Click Startup Script for Windows
REM ============================================================================
REM This script starts the complete BDG prediction system:
REM   1. Validates Python environment
REM   2. Installs missing dependencies
REM   3. Starts API backend server
REM   4. Starts frontend dashboard
REM   5. Monitors health status
REM ============================================================================

setlocal enabledelayedexpansion

REM Color codes (for Windows 10+)
set "GREEN=[32m"
set "RED=[31m"
set "YELLOW=[33m"
set "RESET=[0m"

echo.
echo ============================================================================
echo  BDG PREDICTOR - STARTUP SYSTEM
echo ============================================================================
echo.

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Python executable
set "PYTHON_EXE=python.exe"

REM Check Python is installed
echo [1/5] Checking Python installation...
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('"%PYTHON_EXE%" --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo OK: Python %PYTHON_VERSION% found
echo.

REM Run environment checks
echo [2/5] Running environment checks...
"%PYTHON_EXE%" check_env.py
if errorlevel 1 (
    echo ERROR: Environment checks failed. See logs for details.
    pause
    exit /b 1
)
echo.

REM Install dependencies if needed
echo [3/5] Checking/installing dependencies...
"%PYTHON_EXE%" install_deps.py
if errorlevel 1 (
    echo WARNING: Some dependencies may be missing. Attempting to continue...
)
echo.

REM Start the servers in separate windows
echo [4/5] Starting servers...
echo.

REM Start Backend API Server in new window
echo Starting Backend API Server (port 8787)...
start "BDG Backend API" /B "%PYTHON_EXE%" model_api_server.py --host 127.0.0.1 --port 8787
timeout /t 2 /nobreak >nul

REM Start Frontend Server in new window
echo Starting Frontend Dashboard (port 8000)...
start "BDG Frontend Dashboard" /B "%PYTHON_EXE%" start_frontend.py --host 127.0.0.1 --port 8000
timeout /t 2 /nobreak >nul

echo.
echo [5/5] Starting health monitor...
echo.

REM Start Health Monitor
"%PYTHON_EXE%" health_monitor.py

REM Cleanup on exit
echo.
echo ============================================================================
echo  Startup process completed. Checking server status...
echo ============================================================================
echo.

pause
