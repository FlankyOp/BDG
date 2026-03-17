#!/bin/bash
# BDG Prediction Engine - Startup Script for Linux/Mac

echo ""
echo "========================================"
echo "  BDG GAME PREDICTION ENGINE"
echo "  Linux/macOS Startup Script"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.7+ from https://www.python.org/"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed"
    exit 1
fi

# Check if dependencies are installed
echo "Checking dependencies..."
pip3 show requests > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "✓ All dependencies installed"
echo ""

# Run the main program
echo "Starting BDG Prediction Engine..."
echo ""

python3 main.py "$@"
