# BDG Predictor - One-Click Startup Guide

## Quick Start (⚡ Easiest Way)

### Windows
```bash
# Option 1: Run startup script
startup.bat

# Option 2: Run from PowerShell
python startup.bat
```

### Linux / macOS
```bash
# Option 1: Run startup script
./startup.sh

# Option 2: Run with bash
bash startup.sh
```

---

## What Happens During Startup?

The startup system automatically handles:

1. **Environment Check** - Verifies Python version and configuration
2. **Dependency Installation** - Installs missing packages if needed
3. **Backend Server** - Starts API server on port 8787
4. **Frontend Server** - Starts dashboard on port 8000
5. **Health Monitoring** - Continuously monitors server health

---

## System Requirements

- **Python**: 3.8 or higher (3.13+ recommended)
- **Disk Space**: ~2GB for PyTorch and dependencies
- **Ports**: 8000 (frontend) and 8787 (backend) must be available
- **Network**: Internet for initial setup and API calls

---

## File Structure

```
bdg_predictor/
├── startup.bat              # Windows startup script
├── startup.sh               # Unix/Linux/macOS startup script
├── startup_config.json      # Configuration for startup
├── check_env.py             # Environment validation
├── install_deps.py          # Dependency installer
├── start_frontend.py        # Frontend HTTP server
├── health_monitor.py        # Health monitoring system
├── error_logger.py          # Centralized error logging
├── model_api_server.py      # Backend API server (enhanced)
├── index.html               # Dashboard
├── main.py                  # Prediction CLI
├── logs/                    # Auto-generated logs
│   ├── startup_YYYYMMDD_HHMMSS.log
│   ├── bdg_predictor_YYYYMMDD.log
│   ├── predictions_YYYYMMDD.json
│   └── adaptive_weights.json
└── ...other files
```

---

## Configuration

Edit `startup_config.json` to customize:

```json
{
  "environment": "development",
  "servers": {
    "backend": {
      "host": "127.0.0.1",
      "port": 8787
    },
    "frontend": {
      "host": "127.0.0.1",
      "port": 8000
    }
  },
  "health_check": {
    "interval_seconds": 5
  },
  "features": {
    "auto_install_deps": true,
    "open_browser": true,
    "monitor_health": true
  }
}
```

---

## Manual Mode (If Startup Scripts Don't Work)

### Step 1: Check Environment
```bash
python check_env.py
```

### Step 2: Install Dependencies
```bash
python install_deps.py
```

### Step 3: Start Backend Server (Terminal 1)
```bash
python model_api_server.py --host 127.0.0.1 --port 8787
```

### Step 4: Start Frontend Server (Terminal 2)
```bash
python start_frontend.py --host 127.0.0.1 --port 8000
```

### Step 5: Monitor Health (Terminal 3, optional)
```bash
python health_monitor.py
```

---

## Access Points

Once started:

| Component | URL | Purpose |
|-----------|-----|---------|
| Dashboard | http://localhost:8000 | Main UI |
| Dashboard Health | http://localhost:8000/health | Frontend status |
| API Server | http://localhost:8787 | Backend API |
| API Health | http://localhost:8787/health | Backend status |

---

## Logs & Debugging

All logs are saved to `logs/` directory:

| File | Content |
|------|---------|
| `startup_YYYYMMDD_HHMMSS.log` | Startup process logs |
| `bdg_predictor_YYYYMMDD.log` | Application logs |
| `backend.log` | Backend server logs |
| `frontend.log` | Frontend server logs |
| `predictions_YYYYMMDD.json` | Prediction history |

View logs:
```bash
# Windows
type logs\startup_YYYYMMDD_HHMMSS.log

# Linux/macOS
cat logs/startup_YYYYMMDD_HHMMSS.log
```

---

## Troubleshooting

### ❌ "Port already in use"
**Problem**: Port 8000 or 8787 is already occupied

**Solution**:
```bash
# Find what's using the port (Windows)
netstat -ano | findstr :8000
netstat -ano | findstr :8787

# Find what's using the port (Linux/macOS)
lsof -i :8000
lsof -i :8787

# Either close the existing application or change ports in startup_config.json
```

### ❌ "Module not found"
**Problem**: Python packages not installed

**Solution**:
```bash
python install_deps.py
```

### ❌ "Python not found"
**Problem**: Python not in system PATH

**Solution**:
- Ensure Python 3.8+ is installed
- Add Python to PATH environment variable
- Use `python.exe` or full path explicitly

### ❌ "Firebase config not found"
**Problem**: `firebase-adminsdk.json` missing

**Solution**:
- This is non-critical - the system will work with sample data
- To enable Firebase, add your Firebase service account JSON file

### ⚠️ "Permission denied" (macOS/Linux)
**Problem**: Cannot execute startup.sh

**Solution**:
```bash
chmod +x startup.sh
./startup.sh
```

---

## Dashboard Features

Once running, the dashboard at `http://localhost:8000` provides:

- **Live Draw History**: Last 500 game results in grid view
- **Top 3 Predictions**: Best numbers with confidence scores
- **Real-time Updates**: Auto-refresh as new periods arrive
- **Trend Analysis**: Size, color, and cycle patterns
- **Color Coding**: Visual representation of colors and sizes

---

## Performance Tips

1. **First Run**: Initial dependency installation may take 5-10 minutes
2. **GPU**: Torch will use GPU if available (CUDA), falls back to CPU
3. **Memory**: ~2GB RAM recommended for LSTM model
4. **Network**: API calls fetch live game data - ensure internet connection

---

## Advanced Usage

### Custom Polling Interval
```bash
python main.py --continuous --interval=60 --max-runs=100
```

### Using Sample Data (No API Calls)
```bash
python main.py --sample
```

### Running Examples
```bash
python examples.py
```

---

## Support & Resources

- **GitHub**: https://github.com/FlankyOp/BDG
- **Discord**: https://discord.gg/nKvAfpmEEH
- **Docs**: See `README.md` for detailed documentation

---

## Version Info

- **Startup System**: v1.0.0
- **Python**: 3.8+
- **Required Packages**: See `requirements.txt`

---

*Last Updated: 2026-03-18*
