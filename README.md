# 🎮 BDG Multi-Game Collector

Automatic data collection system for BDG (WinGo) lottery games. Collects data from all 4 game modes (30S, 1M, 3M, 5M) and stores to Firebase Firestore.

## 🚀 Features

- ✅ **Multi-Game Collection** - Polls all 4 WinGo game modes simultaneously
- ✅ **Firebase Integration** - Real-time data storage with Firestore
- ✅ **24/7 Automatic** - Runs on Railway without PC
- ✅ **Pattern Detection** - Analyzes trends, cycles, and patterns
- ✅ **LSTM Model Ready** - Data accumulates for future neural network training

## 📊 Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run collector (all 4 game modes)
python bdg_predictor/multi_game_collector.py

# Or run single prediction
python bdg_predictor/main.py
```

### Cloud Deployment (Railway)

See `RAILWAY_QUICK_START.md` for detailed setup.

**Quick start:**
1. Create repo on GitHub
2. Deploy to Railway.app
3. Add Firebase credentials
4. Done! 24/7 collection runs automatically

## 📁 Project Structure

```
bdg_predictor/
├── multi_game_collector.py    # Main collector (polls all 4 modes)
├── main.py                    # Legacy single-mode predictor
├── firebase_client.py         # Firebase admin SDK wrapper
├── config.py                  # Configuration & environment vars
├── pattern_detector.py        # Pattern & cycle detection
├── probability_engine.py      # Scoring & ranking engine
├── predictor.py               # Prediction orchestrator
├── data_fetcher.py            # API data fetching
└── models/                    # Trained LSTM models (9.5 MB)

assets/
├── js/app.js                  # Frontend logic
└── ...

# Deployment
Procfile                       # Railway process definition
runtime.txt                    # Python version
requirements.txt              # Dependencies
```

## 🔐 Security

**Sensitive files are NOT committed:**
- ✅ `firebase-adminsdk.json` - Excluded via `.gitignore`
- ✅ `.env` - Excluded (use `.env.example` as template)
- ✅ `logs/` - Excluded
- ✅ Large models `*.pt` - Excluded

**Environment variables:**
```bash
# Copy template
cp .env.example .env

# Set your values
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/firebase-adminsdk.json
```

On Railway, upload credentials via Variables tab.

## 📊 Data Collection

Collects to Firebase `bdg_history` collection:
- `period` - Game period ID
- `number` - Draw result (0-9)
- `color` - Red/Green/Violet
- `size` - Small/Big
- `game_code` - WinGo_30S / 1M / 3M / 5M
- `ts` - Server timestamp

## 🤖 Future: LSTM Training

Once 1000+ draws collected:

1. **Export data** from Firebase Firestore
2. **Train** LSTM model in Google Colab
3. **Save** model to Google Drive
4. **Deploy** trained model to production
5. Website uses it for live predictions

## 📝 Configuration

All settings in `bdg_predictor/config.py`:

```python
HISTORY_DRAWS_LIMIT = 500          # Fetch last 500 draws
ENABLE_SELF_LEARNING = True        # Adaptive weight tuning
LSTM_ENABLED = True                # Neural network fallback
...
```

Override via environment variables:
```bash
export BDG_HISTORY_DRAWS_LIMIT=1000
export BDG_LSTM_ENABLED=false
```

## 🔧 Troubleshooting

**Firebase not connecting:**
- Check `firebase-adminsdk.json` exists
- Verify credentials path in `.env`
- Check Firebase rules allow writes

**API timeouts:**
- Increase `BDG_API_TIMEOUT` in config
- Check internet connection
- API may be rate-limiting

**Missing dependencies:**
```bash
pip install -r requirements.txt
```

## 📖 Files Reference

- `RAILWAY_QUICK_START.md` - Quick Railway deployment guide
- `RAILWAY_DEPLOY.md` - Detailed Railway setup with troubleshooting
- `check_railway_deployment.py` - Pre-deployment verification script
- `.env.example` - Environment variables template

## 📄 License

Private project. Do not share credentials.

## 🎯 Next Steps

1. ✅ Deploy to Railway
2. ✅ Collect data for 1 week
3. Train LSTM in Google Colab
4. Deploy trained model
5. Live predictions active

---

**Status:** ✅ Ready for Production

Last updated: 2026-03-18
