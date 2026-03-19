#!/bin/bash

################################################################################
# BDG Predictor - One-Click Startup Script for Unix/Linux/macOS
################################################################################
# This script starts the complete BDG prediction system:
#   1. Validates Python environment
#   2. Installs missing dependencies
#   3. Starts API backend server
#   4. Starts frontend dashboard
#   5. Monitors health status
################################################################################

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Python executable
PYTHON_EXE="python3"

# PID tracking
BACKEND_PID=""
FRONTEND_PID=""
MONITOR_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down servers..."
    
    if [ ! -z "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$MONITOR_PID" ] && kill -0 "$MONITOR_PID" 2>/dev/null; then
        kill "$MONITOR_PID" 2>/dev/null || true
    fi
    
    echo "Servers stopped."
    exit 0
}

# Setup signal handlers
trap cleanup SIGINT SIGTERM EXIT

echo ""
echo "============================================================================"
echo " BDG PREDICTOR - STARTUP SYSTEM"
echo "============================================================================"
echo ""

# Check Python is installed
echo "[1/5] Checking Python installation..."
if ! command -v "$PYTHON_EXE" &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 not found. Please install Python 3.8+ and ensure it's in PATH.${NC}"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_EXE" --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}OK: Python $PYTHON_VERSION found${NC}"
echo ""

# Run environment checks
echo "[2/5] Running environment checks..."
"$PYTHON_EXE" check_env.py
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Environment checks failed. See logs for details.${NC}"
    exit 1
fi
echo ""

# Install dependencies if needed
echo "[3/5] Checking/installing dependencies..."
"$PYTHON_EXE" install_deps.py
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}WARNING: Some dependencies may be missing. Attempting to continue...${NC}"
fi
echo ""

# Start the servers
echo "[4/5] Starting servers..."
echo ""

# Start Backend API Server
echo -e "${GREEN}Starting Backend API Server (port 8787)...${NC}"
"$PYTHON_EXE" model_api_server.py --host 127.0.0.1 --port 8787 > logs/backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

# Start Frontend Server
echo -e "${GREEN}Starting Frontend Dashboard (port 8000)...${NC}"
"$PYTHON_EXE" start_frontend.py --host 127.0.0.1 --port 8000 > logs/frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 2

echo ""
echo "[5/5] Starting health monitor..."
echo ""

# Start Health Monitor
"$PYTHON_EXE" health_monitor.py &
MONITOR_PID=$!

# Wait for monitor (or any process termination)
wait

