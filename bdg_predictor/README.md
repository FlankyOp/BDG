# BDG Prediction Engine

> Automatic pattern analysis and next-number prediction for BDG / WinGo lottery games.
> Comes with a **live browser dashboard** (`index.html`) and a **Python CLI** (`main.py`).

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Game Rules](#game-rules)
5. [How It Works](#how-it-works)
6. [Live API Endpoints](#live-api-endpoints)
7. [Python Module API](#python-module-api)
8. [CLI Reference](#cli-reference)
9. [Configuration](#configuration)
10. [Prediction Output Format](#prediction-output-format)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The engine fetches live draw history from the WinGo public API, runs multi-layer pattern analysis across up to the last **500 draws**, and outputs the top-3 most probable next numbers with confidence scores.

```
Live WinGo API
      │
      ▼
 DataFetcher          ← fetches up to 500 history entries (retry logic)
      │
      ▼
 PatternDetector      ← size · color · cycle · frequency patterns
      │
      ▼
 ProbabilityEngine    ← weighted confidence scoring (6 factors)
      │
      ▼
 Predictor            ← ranks all 10 numbers, picks top 3
      │
      ├──▶ Python CLI   (main.py)
      └──▶ Browser dashboard  (index.html)
```

---

## Quick Start

### Browser Dashboard

Open directly in any browser — no install or server needed:

```
bdg_predictor/index.html
```

Auto-fetches live data, displays up to **500 historical results** in a scrollable chip grid, and re-predicts on every new period.

### Python CLI

```bash
pip install -r requirements.txt
cd bdg_predictor
python main.py          # interactive menu
python main.py --sample # quick single prediction, no API calls
```

---

## Project Structure

```
bdg_predictor/
├── index.html            # Dashboard markup shell
├── assets/
│   ├── css/styles.css    # Dashboard styles
│   └── js/app.js         # Dashboard logic (including API polling)
├── main.py               # CLI entry point & PredictionEngine controller
├── predictor.py          # Orchestrates PatternDetector + ProbabilityEngine
├── pattern_detector.py   # Size / color / cycle pattern detection
├── probability_engine.py # Weighted confidence score calculation
├── data_fetcher.py       # HTTP client for WinGo API (with retry)
├── config.py             # Global constants + TestSuite
├── examples.py           # 12 runnable usage examples (menu-driven)
├── requirements.txt      # Python dependencies (requests only)
└── logs/                 # Auto-created: daily .log + predictions .json
```

---

## Game Rules

### Size Mapping

| Number | Size  |
|--------|-------|
| 0 – 4  | Small |
| 5 – 9  | Big   |

### Color Mapping

| Number | Color  |
|--------|--------|
| 0      | Red    |
| 1      | Green  |
| 2      | Red    |
| 3      | Green  |
| 4      | Red    |
| 5      | Violet |
| 6      | Red    |
| 7      | Green  |
| 8      | Red    |
| 9      | Green  |

---

## How It Works

### 1 · Data Fetching

`DataFetcher` retrieves draw history via the public WinGo JSON endpoints.
Each HTTP request uses **exponential-backoff retry** (up to 3 attempts: 0 s → 1 s → 2 s).
The browser dashboard tries `pageSize=500` first, then falls back to the default endpoint.

### 2 · Pattern Detection

`PatternDetector` runs four independent analyses using large-history context (up to 500 draws).

#### Size Patterns

| Pattern | Window | Trigger |
|---------|--------|---------|
| **Alternating** | Last 15 draws | ≥ 90 % of consecutive transitions flip Big ↔ Small |
| **Repeating pairs** | Last 10 draws | All BB/SS pairs match the first pair |
| **Streak** | Full history | Same size ≥ 3 consecutive times |

#### Color Patterns

| Pattern | Window | Description |
|---------|--------|-------------|
| **nAnB** (n = 1–4) | Last 12 colors | n identical colors then n of another (e.g. RRGG = 2A2B) |
| **Color cycle** | Last 9 colors | Repeating 2- or 3-color sequence with ≥ 75 % match ratio |
| **Dominant color** | All draws | Most frequent color over the sample |

#### Number Cycles

Checks 2-, 3-, 4-, and 6-round cycles using a **4× confirmation window**.
A cycle is confirmed when > 60 % of positions match the candidate pattern.

#### Frequency Analysis

Counts occurrences of each digit 0–9.
Numbers absent in recent draws receive a bias boost.

---

### 3 · Probability Engine

Six weights are combined into one **confidence score** (0 – 100 %):

```
Confidence = TrendWeight     × 0.30
           + FrequencyWeight × 0.25
           + CycleWeight     × 0.20
           + StreakWeight    × 0.15
           + NoiseWeight     × 0.10
           + ColorWeight     × 0.05  (only when a color pattern is active)
```

| Weight | Logic |
|--------|-------|
| **Trend** | Boosts opposite-size numbers when a streak is detected; applies size-balance boost when one size dominates last 5 draws |
| **Frequency** | Inverse of historical frequency — favors underrepresented digits |
| **Cycle** | Boosts the number predicted by the strongest detected cycle |
| **Streak** | Strong boost (clamped to 1.0) for the opposite size when streak ≥ 3 |
| **Noise** | Small nudge for numbers absent in the last 3 draws |
| **Color** | Boosts the color predicted by a nAnB or color-cycle pattern |

All 10 digits are scored; the **top 3** become Primary, Alternative, and Strong Possibility.

### 4 · Self-Learning Weights

The Python engine maintains an adaptive weight profile in `logs/adaptive_weights.json`.
After each new actual result arrives, the profile is nudged toward factors that supported successful predictions and gently reduced for factors behind misses.

---

## Live API Endpoints

### Base URL

```
https://draw.ar-lottery01.com/WinGo
```

### Game Codes

| Code | Interval |
|------|----------|
| `WinGo_1M` | 1 minute  |
| `WinGo_3M` | 3 minutes |
| `WinGo_5M` | 5 minutes |

---

### GET — Live State

```
GET /WinGo/{gameCode}.json?ts={unix_ms}
```

Returns the active and upcoming period plus the countdown end-time.

**Example request:**
```
https://draw.ar-lottery01.com/WinGo/WinGo_1M.json?ts=1742000000000
```

**Response shape:**
```json
{
  "current": {
    "issueNumber": "20260317100011227",
    "endTime": 1742000060000
  },
  "next": {
    "issueNumber": "20260317100011228"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `current.issueNumber` | string | Active period ID |
| `current.endTime` | number | Unix ms when the round closes |
| `next.issueNumber` | string | Upcoming period ID |

---

### GET — Draw History

```
GET /WinGo/{gameCode}/GetHistoryIssuePage.json?pageSize={n}&pageNo={p}&ts={unix_ms}
```

Returns paginated draw history, newest first.

**Example request:**
```
https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json?pageSize=500&pageNo=1&ts=1742000000000
```

**Response shape:**
```json
{
  "data": {
    "list": [
      {
        "issueNumber": "20260317100011226",
        "number": "7",
        "color": "green"
      }
    ],
    "total": 500
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data.list` | array | Draw records, newest first |
| `data.list[].issueNumber` | string | Period ID |
| `data.list[].number` | string | Drawn digit 0–9 |
| `data.list[].color` | string | `"red"`, `"green"`, `"green,violet"`, etc. |
| `data.total` | number | Total available records |

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pageSize` | API default | Records per page (try `500` for bulk fetch) |
| `pageNo` | `1` | Page number (1-based) |
| `ts` | — | Cache-busting timestamp (Unix ms) |

---

## Python Module API

### `Predictor`

```python
from predictor import Predictor

p = Predictor(draws: List[int], period: Optional[str] = None)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `.generate_prediction()` | `dict` | Full prediction payload |
| `.print_prediction()` | `dict` | Generates + pretty-prints to console, returns dict |
| `.get_quick_prediction()` | `dict` | Compact: best number, color, size, confidence |

`generate_prediction()` keys:

```
timestamp, current_period, next_period,
primary_prediction      { number, size, color, accuracy }
alternative_prediction  { number, size, color, accuracy } | null
strong_possibility      { number, size, color, accuracy } | null
trend_analysis          { size_pattern, color_pattern, active_streak, detected_cycle }
probability_explanation str
summary                 { best_bet, alternative_bet, backup_bet, combined_strategy }
```

---

### `PatternDetector`

```python
from pattern_detector import PatternDetector

d = PatternDetector(draws: List[int])
```

| Method | Returns | Description |
|--------|---------|-------------|
| `.analyze_all_patterns()` | `dict` | Runs all detectors, unified result |
| `.detect_size_pattern()` | `dict` | Alternating / Repeating / Streak analysis |
| `.detect_color_pattern()` | `dict` | nAnB / Color Cycle / Dominant color |
| `.detect_cycles()` | `list` | Detected numeric cycles sorted by strength |
| `.get_number_frequency()` | `dict[int,int]` | Occurrence count per digit 0–9 |
| `.get_size_distribution()` | `dict[str,int]` | `{ "Big": n, "Small": m }` |

---

### `ProbabilityEngine`

```python
from probability_engine import ProbabilityEngine

e = ProbabilityEngine(draws: List[int], patterns: dict)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `.get_top_predictions(n=3)` | `list[dict]` | Top-n predictions with rank, score, size, color |
| `.rank_all_numbers()` | `list[tuple]` | All 10 digits sorted by confidence score desc |
| `.calculate_confidence_score(number)` | `float` | Score 0.0–1.0 for one digit |
| `.explain_prediction(number)` | `dict` | Per-factor weight breakdown as % strings |
| `.get_probability_analysis()` | `dict` | Full analysis with primary / alternative / backup |

---

### `DataFetcher`

```python
from data_fetcher import DataFetcher

f = DataFetcher()
```

| Method | Returns | Description |
|--------|---------|-------------|
| `.fetch_past_draws(period, game_type=None)` | `dict\|None` | Fetches live history; retries up to 3×; falls back to legacy URL |
| `.extract_draws(data)` | `list[dict]` | Parses raw API response into `[{period, number}]` |
| `.get_latest_draws(limit=30)` | `list[int]` | Most recent `limit` draw numbers |
| `.get_next_period(current)` | `str` | Increments a period ID string by 1 |

---

### `PredictionEngine` (CLI controller)

```python
from main import PredictionEngine

engine = PredictionEngine(use_sample_data: bool = False)
```

| Method | Description |
|--------|-------------|
| `.run_single_prediction(period=None)` | One full prediction cycle |
| `.run_continuous_polling(interval_seconds=30, max_runs=None)` | Polling loop; `None` = infinite |
| `.analyze_recent_predictions(num=5)` | Prints summary of recent history |
| `.export_predictions(filename=None)` | Saves session history to JSON |

---

### Helper Classes

```python
from pattern_detector import SizeMapper, ColorMapper

SizeMapper.get_size(n: int)   # → "Big" | "Small"
ColorMapper.get_color(n: int) # → "Red" | "Green" | "Violet"
```

---

## CLI Reference

```
python main.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| *(none)* | — | Opens interactive 6-option menu |
| `--sample` / `-s` | off | Built-in sample data, no API calls |
| `--continuous` / `-c` | off | Start polling immediately |
| `--interval=N` | `30` | Seconds between polls |
| `--max-runs=N` | unlimited | Stop after N predictions |

**Examples:**

```bash
# One prediction, no network
python main.py --sample

# Live polling every 60 s, stop after 20 rounds
python main.py --continuous --interval=60 --max-runs=20
```

### Running Examples

```bash
python examples.py       # interactive menu (12 examples)
python examples.py 12    # run example 12 directly (benchmark)
```

### Running the Test Suite

```bash
python config.py
```

---

## Configuration

Edit `config.py → Config` to tune the engine:

```python
PREFERRED_DRAWS    = 30    # draws used for analysis
MIN_DRAWS_REQUIRED = 10    # minimum before predicting

# Confidence score weights (sum = 1.0)
WEIGHT_TREND     = 0.30
WEIGHT_FREQUENCY = 0.25
WEIGHT_CYCLE     = 0.20
WEIGHT_STREAK    = 0.15
WEIGHT_NOISE     = 0.10

# Boost factors
SIZE_BALANCE_BOOST = 0.15
COLOR_BOOST        = 0.18
MIN_STREAK_LENGTH  = 3

# Thresholds
HIGH_CONFIDENCE   = 0.75
MEDIUM_CONFIDENCE = 0.50
LOW_CONFIDENCE    = 0.30
```

---

## Prediction Output Format

```
============================================================
         BDG GAME PREDICTION ENGINE
============================================================

Next Period: 20260317100011228

PRIMARY PREDICTION
----------------------------------------
Number:   7      Size: Big      Color: Green      Accuracy: 34.5%

ALTERNATIVE PREDICTION
----------------------------------------
Number:   5      Size: Big      Color: Violet     Accuracy: 28.1%

STRONG POSSIBILITY
----------------------------------------
Number:   2      Size: Small    Color: Red        Accuracy: 22.7%

TREND ANALYSIS
----------------------------------------
Size Pattern:    Alternating Pattern (88%)
Color Pattern:   2A2B (70%)
Active Streak:   No active streak
Detected Cycle:  3-round cycle (Strength: 82%)

PROBABILITY EXPLANATION
----------------------------------------
Based on: Trend analysis (35%), Cycle detection (25%)

FINAL SUMMARY
----------------------------------------
Best Bet:        NUMBER 7 (Green, Big)
Alternative Bet: NUMBER 5 (Violet, Big)
Backup Bet:      NUMBER 2 (Red, Small)
Strategy:        Play 7 with 35% confidence. Backup with 5 if needed.
============================================================
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dashboard shows "Offline" | CORS block or API down | Check browser console; use CLI with `--sample` for testing |
| `pip install` fails | Old requirements format | File uses `#` comments — re-pull and retry |
| "Insufficient draw data" | API returned < 10 draws | Engine auto-falls back to sample data |
| Low confidence (< 20 %) | No strong pattern signal | Normal for random data — use all top-3 for coverage |
| `KeyboardInterrupt` in poll loop | Expected | Ctrl+C stops cleanly; session summary is printed |

### Log Files

| File | Description |
|------|-------------|
| `logs/bdg_predictor_YYYYMMDD.log` | Full application log |
| `logs/predictions_YYYYMMDD.json` | All predictions from the day as a JSON array |

---

*Version 1.1.0 · Updated 2026-03-17*
