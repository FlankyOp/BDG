# 🎯 FlankyGoD BDG Engine V12

A real-time prediction dashboard for WinGo (91Club / BDG) draw games. Combines live API polling, statistical pattern analysis, an LSTM neural network, and an automated Martingale betting system.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
python install_deps.py
```

### 2. Start the Model API server (port 8787)
```bash
python model_api_server.py --port 8787
```

### 3. Start the frontend server (port 8000)
```bash
python start_frontend.py
```

### 4. Open the dashboard
```
http://127.0.0.1:8000/index.html
```

Or use the one-click startup scripts:
- **Windows:** `startup.bat`
- **Linux/Mac:** `startup.sh`

---

## ⚠️ Critical Architecture Notes (Read Before Changing Anything)

> These are hard-won lessons. Breaking any of these will cause the "Syncing with real-time API..." stall.

### 1. `API_BASE` must point to the external draw API
```js
// ✅ CORRECT
const API_BASE = "https://draw.ar-lottery01.com";

// ❌ WRONG — this kills all data fetching
const API_BASE = "http://127.0.0.1:8787"; // do NOT set this!
```
`MODEL_API_BASE` (port 8787) is **only** for the LSTM inference server. `API_BASE` is the live draw data source.

### 2. The draw API uses simple GET requests — no POST, no JSON body
```js
// ✅ CORRECT
const url = `${API_BASE}/WinGo/${currentGame}/GetHistoryIssuePage.json?pageSize=500&pageNo=1`;
fetch(url, { method: 'GET', cache: 'no-store' });

// ❌ WRONG — the API does NOT accept POST with JSON body
fetch(url, { method: 'POST', body: JSON.stringify({...}) });
```

### 3. The API supports CORS natively — no proxy needed
`draw.ar-lottery01.com` sends `Access-Control-Allow-Origin: *`. You do **not** need a backend proxy. Adding one will only create 404/403 errors.

### 4. The draw API response format
```json
{
  "data": {
    "list": [
      { "issueNumber": "...", "number": 5, "colour": "green", "size": "big" },
      ...
    ]
  }
}
```
Fields to read: `json?.data?.list || json?.list`

### 5. Two separate servers — do NOT mix them
| Server | Port | File | Purpose |
|--------|------|------|---------|
| Frontend | 8000 | `start_frontend.py` | Serves `index.html` |
| Model API | 8787 | `model_api_server.py` | LSTM inference only |

### 6. Prediction hierarchy is Number → Size → Color
This is intentional user preference. Do not reorder or equalise the weights.

---



```
bdg_predictor/
├── index.html              # Main dashboard UI (single-page app)
├── main.py                 # Core orchestration & data pipeline
├── model_api_server.py     # Lightweight HTTP server for LSTM inference
├── start_frontend.py       # Static file server for the dashboard
├── config.py               # All tunable parameters
├── predictor.py            # Rule-based prediction engine
├── probability_engine.py   # Weighted ensemble predictions
├── pattern_detector.py     # FFT, streak, and cycle detectors
├── sequence_model.py       # LSTM model definition & training
├── firebase_client.py      # Firebase Realtime Database sync
├── data_fetcher.py         # Live API polling
├── health_monitor.py       # Service health checks
├── firebase-adminsdk.json  # Firebase service account (keep private!)
└── models/                 # Trained model checkpoints
    └── advanced/
        ├── WinGo_30S/best.pt
        ├── WinGo_1M/best.pt
        └── ...
```

---

## 🎮 Game Modes

| Mode | Interval | API TypeId |
|------|----------|------------|
| WinGo 30S | 30 seconds | 1 |
| WinGo 1M  | 1 minute   | 2 |
| WinGo 3M  | 3 minutes  | 3 |
| WinGo 5M  | 5 minutes  | 4 |

---

## 🔗 Data Source (API)

Live draw history is fetched directly from:

```
GET https://draw.ar-lottery01.com/WinGo/{game}/GetHistoryIssuePage.json?pageSize=500&pageNo=1
```

**Example:**
```
https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json?pageSize=200&pageNo=1
```

The API returns JSON with draw results including `issueNumber`, `number`, `colour`, and `size`.

---

## 🧠 Prediction System

Predictions are generated via a **weighted ensemble** of 4 signals:

| Signal | Method | Weight |
|--------|--------|--------|
| **Number** | LSTM Neural Network + Statistical frequency | Highest |
| **Size** | Big/Small streak analysis | Medium |
| **Color** | Red/Green/Violet cycle detection | Lowest |

> Hierarchy is **Number → Size → Color** (per user preference)

### Key Components
- **FFT Analysis** — Detects repeating cycles in draw sequences
- **Martingale Betting** — Auto-scales bets: `1 × 3^n` levels (Rs 1 → Rs 177,147)
- **Firebase Sync** — Persists history across sessions via Realtime Database
- **LocalStorage Cache** — Near-instant loads on page refresh

---

## 💰 Auto-Betting System

- Predictions are made before each draw
- On win: bet resets to level 1
- On loss: bet escalates to next Martingale level
- Risk cap: max 30% of current balance per bet
- Payouts: Numbers = 9×, Size/Color = 1.95×

---

## ⚙️ Configuration (`config.py`)

Key parameters you can tune:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FFT_MIN_STRENGTH` | 0.3 | Minimum FFT signal strength to use cycle prediction |
| `ENSEMBLE_DAMPING` | 0.85 | Confidence dampening factor |
| `RISK_CAP` | 0.30 | Max fraction of balance for a single bet |
| `HISTORY_WINDOW` | 500 | Number of past draws to analyze |

---

## 🔥 Firebase Setup

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Realtime Database**
3. Download the Admin SDK JSON → save as `firebase-adminsdk.json`
4. Add your web config to `index.html` (look for `firebaseConfig`)

> ⚠️ Never commit `firebase-adminsdk.json` to public repos!

---

## 🛠️ Development Notes

- The dashboard polls the live API every **~2 seconds** for new draws
- The `model_api_server.py` is a pure-stdlib HTTP server (no Flask/FastAPI needed)
- All predictions happen client-side in `index.html` for zero-latency UX
- The LSTM model runs on-demand via `POST /api/advanced/predict`

---

## 📊 Accuracy

Results are inherently probabilistic — WinGo is a pseudo-random game. The engine is designed to detect **short-term statistical biases** in the sequence, not to guarantee outcomes.

> Track your win rate in the Stats panel on the dashboard.

---

## 📝 License

Private project — FlankyGoD. Not for public distribution.
