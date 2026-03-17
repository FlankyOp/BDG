# Project Guidelines

## Code Style
- Use Python type hints throughout backend changes.
- Keep logging through Python `logging` (do not replace with `print` except existing console output formatting paths).
- Keep constants centralized in `config.py`.
- For frontend, preserve current single-page structure in `index.html` and existing DOM ids/classes unless a task explicitly requires structural changes.
- For `index.html`, prefer additive edits (add blocks/functions) over removing existing sections unless explicitly requested.

## Architecture
- Backend prediction flow is:
  WinGo API -> `data_fetcher.py` -> `pattern_detector.py` -> `probability_engine.py` -> `predictor.py` -> `main.py`.
- Firebase writes happen through `firebase_client.py`.
- Frontend is static and runtime-driven:
  `index.html` + `assets/js/app.js` (+ `assets/css/styles.css` for style variants).
- Treat `predictor.py` as orchestrator only; keep heavy scoring logic inside `probability_engine.py` and pattern extraction in `pattern_detector.py`.

## Build and Test
- Install dependencies:
  - `pip install -r requirements.txt`
- Run backend (Windows):
  - `cd bdg_predictor`
  - `.\run.bat` or `python main.py`
- Run backend (sample/offline mode):
  - `python main.py --sample`
- Syntax checks commonly used in this repo:
  - `python -m compileall .\bdg_predictor`
  - `node --check .\bdg_predictor\assets\js\app.js`

## Conventions
- Draw numbers are 0-9.
- Size mapping: 0-4 -> Small, 5-9 -> Big.
- Color mapping includes Red/Green with Violet combinations for 0 and 5.
- Period IDs are string-like large numeric values; avoid lossy numeric conversions in frontend JS except where explicitly handled (BigInt for next period).
- Keep prediction payload compatibility for frontend fields:
  - `primary_prediction`, `alternative_prediction`, `strong_possibility`
  - `trend_analysis`, `summary`, `timestamp`, `next_period`

## Pitfalls
- Firebase Admin requires a real service key JSON (`firebase-adminsdk.json`) or `FIREBASE_SERVICE_ACCOUNT_PATH` env var; placeholder JSON will fail runtime writes.
- Realtime DB URL mismatches can silently break frontend sync paths.
- Do not commit secrets; frontend Firebase config is public app config only, not admin credentials.
- The frontend is highly stateful; when changing polling/timer logic, avoid introducing overlapping fetch loops or duplicate timers.
