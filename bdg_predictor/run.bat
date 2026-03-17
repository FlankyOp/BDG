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

REM Run the main program
echo Starting BDG Prediction Engine...
echo.

python main.py %*

pause
