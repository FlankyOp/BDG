import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_BASE_DIR)

def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""): return default
    try: return int(value)
    except ValueError: return default

def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""): return default
    try: return float(value)
    except ValueError: return default

def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""): return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

class Config:
    # API Settings
    API_BASE_URL = _env_str("BDG_API_BASE_URL", "https://draw.ar-lottery01.com")
    API_TIMEOUT = _env_int("BDG_API_TIMEOUT", 10)
    GAME_CODE = _env_str("BDG_GAME_CODE", "WinGo_30S")
    
    # Pattern Detection
    MIN_DRAWS_REQUIRED = 10
    PREFERRED_DRAWS = 30
    HISTORY_DRAWS_LIMIT = 500
    
    # Weights
    WEIGHT_SEQUENCE = 0.45
    WEIGHT_TREND = 0.20
    WEIGHT_CYCLE = 0.15
    WEIGHT_FREQUENCY = 0.10
    WEIGHT_STREAK = 0.10
    WEIGHT_NOISE = 0.00

    # Self-learning
    ENABLE_SELF_LEARNING = True
    LEARNING_RATE = 0.08
    MIN_WEIGHT_FLOOR = 0.05

    # LSTM Settings
    LSTM_ENABLED = True
    LSTM_MODEL_DIR = os.path.join(_ROOT_DIR, "models")
    LSTM_MODEL_PATH = os.path.join(LSTM_MODEL_DIR, "sequence_lstm.pt")
    WEIGHT_LSTM = 0.30
    
    # Boost factors
    SIZE_BALANCE_BOOST = 0.15
    COLOR_BOOST = 0.18
    COLOR_BLEND_WEIGHT = 0.05
    MIN_STREAK_LENGTH = 3

    # Sequence Settings
    SEQUENCE_LOOKBACK_DRAWS = 500
    SEQUENCE_MAX_CONTEXT = 3
    FFT_MIN_STRENGTH = 0.45
