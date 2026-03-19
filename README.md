# BDG Collector

Simple collector for WinGo data.

It fetches draws from all game modes and stores them in Firebase Firestore.

## What It Does

- Polls WinGo_30S, WinGo_1M, WinGo_3M, and WinGo_5M
- Stores new draw rows in the `bdg_history` collection
- Keeps `period`, `number`, `color`, `size`, `game_code`, and timestamp

## Run Locally

```bash
pip install -r requirements.txt
python bdg_predictor/multi_game_collector.py
```

For single-run prediction/testing:

```bash
python bdg_predictor/main.py
```

## Deploy

Use Railway for always-on collection.

- Quick guide: `RAILWAY_QUICK_START.md`
- Full guide: `RAILWAY_DEPLOY.md`

## Setup

1. Add Firebase service account JSON at `bdg_predictor/firebase-adminsdk.json`
2. Keep secrets out of git (`.gitignore` already excludes them)
3. Optional: copy `.env.example` to `.env` and adjust values

## Owner

- GitHub: FlankyOp
- Discord: https://discord.gg/nKvAfpmEEH

## Credentials

- Keep private credentials only in local `.env` or Railway Variables.
- Do not place secrets in tracked files.
- Firebase service account should stay as `bdg_predictor/firebase-adminsdk.json` locally or be uploaded as a private file variable on Railway.

## Notes

- This repo is private project code.
- Do not commit credentials.
- Collected data can be used later for model training in Colab.
