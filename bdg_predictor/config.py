"""
Configuration and Testing Module
Provides utilities for testing and configuration management.
"""

import logging
import os
from typing import Any, Dict, List
# NOTE: Predictor and create_sample_data are imported lazily inside each
# TestSuite method to avoid a circular import chain:
#   probability_engine → config → predictor → probability_engine

logger = logging.getLogger(__name__)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if not value:
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Application configuration with environment-variable overrides.

    Non-obvious knobs:
    - `MIN_WEIGHT_FLOOR`: lower bound applied before adaptive weight normalization.
    - `SIZE_BALANCE_BOOST`: bonus when recent Big/Small distribution is skewed.
    - `COLOR_BOOST`: color-match bonus for explicit color pattern alignment.
    - `COLOR_BLEND_WEIGHT`: fraction of color score blended into total confidence.
    """
    
    # API Settings
    API_BASE_URL = _env_str("BDG_API_BASE_URL", "https://draw.ar-lottery01.com")
    API_TIMEOUT = _env_int("BDG_API_TIMEOUT", 10)
    GAME_CODE = _env_str("BDG_GAME_CODE", "WinGo_1M")
    
    # Polling Settings
    DEFAULT_POLLING_INTERVAL = _env_int("BDG_DEFAULT_POLLING_INTERVAL", 30)
    DEFAULT_POLL_LIMIT = _env_int("BDG_DEFAULT_POLL_LIMIT", 10)
    
    # Pattern Detection
    MIN_DRAWS_REQUIRED = _env_int("BDG_MIN_DRAWS_REQUIRED", 10)
    PREFERRED_DRAWS = _env_int("BDG_PREFERRED_DRAWS", 30)
    HISTORY_DRAWS_LIMIT = _env_int("BDG_HISTORY_DRAWS_LIMIT", 500)
    
    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_DIR = _env_str("BDG_LOG_DIR", "logs")
    
    # Confidence Thresholds
    HIGH_CONFIDENCE = _env_float("BDG_HIGH_CONFIDENCE", 0.75)
    MEDIUM_CONFIDENCE = _env_float("BDG_MEDIUM_CONFIDENCE", 0.50)
    LOW_CONFIDENCE = _env_float("BDG_LOW_CONFIDENCE", 0.30)
    
    # Weights for probability calculation
    # Model Weights (Total should be ~1.0)
    WEIGHT_SEQUENCE = _env_float("BDG_WEIGHT_SEQUENCE", 0.45) # Increased from 0.3
    WEIGHT_TREND = _env_float("BDG_WEIGHT_TREND", 0.20)
    WEIGHT_CYCLE = _env_float("BDG_WEIGHT_CYCLE", 0.15)
    WEIGHT_FREQUENCY = _env_float("BDG_WEIGHT_FREQUENCY", 0.10)
    WEIGHT_STREAK = _env_float("BDG_WEIGHT_STREAK", 0.10)
    WEIGHT_NOISE = _env_float("BDG_WEIGHT_NOISE", 0.00) # Adjusted to make total 1.0

    # Self-learning (adaptive weight tuning)
    ENABLE_SELF_LEARNING = _env_bool("BDG_ENABLE_SELF_LEARNING", True)
    LEARNING_RATE = _env_float("BDG_LEARNING_RATE", 0.08)
    MIN_WEIGHT_FLOOR = _env_float("BDG_MIN_WEIGHT_FLOOR", 0.05)

    # Sequence learner (Markov)
    SEQUENCE_LOOKBACK_DRAWS = _env_int("BDG_SEQUENCE_LOOKBACK_DRAWS", HISTORY_DRAWS_LIMIT)
    SEQUENCE_MAX_CONTEXT = _env_int("BDG_SEQUENCE_MAX_CONTEXT", 3)

    # Deep sequence model (LSTM — requires: pip install torch)
    LSTM_ENABLED = _env_bool("BDG_LSTM_ENABLED", True)
    LSTM_MODEL_DIR = _env_str("BDG_LSTM_MODEL_DIR", os.path.join(_BASE_DIR, "models"))
    LSTM_MODEL_PATH = os.path.join(LSTM_MODEL_DIR, "sequence_lstm.pt")
    WEIGHT_LSTM = _env_float("BDG_WEIGHT_LSTM", 0.30)
    
    # FFT Seasonality Settings
    FFT_MIN_STRENGTH = _env_float("BDG_FFT_MIN_STRENGTH", 0.45)
    FFT_WINDOW_SIZE = _env_int("BDG_FFT_WINDOW_SIZE", 256)
    
    # Ensemble Settings
    ENSEMBLE_DAMPING = _env_float("BDG_ENSEMBLE_DAMPING", 0.15)
    
    # Boost factors
    SIZE_BALANCE_BOOST = _env_float("BDG_SIZE_BALANCE_BOOST", 0.15)
    COLOR_BOOST = _env_float("BDG_COLOR_BOOST", 0.18)
    COLOR_BLEND_WEIGHT = _env_float("BDG_COLOR_BLEND_WEIGHT", 0.05)
    MIN_STREAK_LENGTH = _env_int("BDG_MIN_STREAK_LENGTH", 3)


class TestSuite:
    """Comprehensive test suite for the prediction engine."""
    
    @staticmethod
    def test_single_prediction():
        """Test single prediction with sample data."""
        from predictor import Predictor  # type: ignore
        from data_fetcher import create_sample_data  # type: ignore
        print("\n" + "="*60)
        print("TEST: Single Prediction with Sample Data")
        print("="*60)

        draws = create_sample_data()
        print(f"Sample draws: {draws}")
        
        predictor = Predictor(draws, period="20260317100011227")
        prediction = predictor.print_prediction()
        
        return prediction
    
    @staticmethod
    def test_pattern_detection() -> List[Dict[str, Any]]:
        """Test pattern detection accuracy."""
        from predictor import Predictor  # type: ignore
        print("\n" + "="*60)
        print("TEST: Pattern Detection")
        print("="*60)

        test_cases: List[Dict[str, Any]] = [
            {
                "name": "Alternating Small/Big",
                "draws": [1, 5, 2, 6, 3, 7, 4, 8, 0, 9, 1, 5, 2, 6, 3, 7, 4, 8, 0, 9],
                "expected_pattern": "Alternating"
            },
            {
                "name": "Repeating 2-Pair",
                "draws": [1, 1, 5, 5, 2, 2, 6, 6, 3, 3, 7, 7, 4, 4, 8, 8, 0, 0, 9, 9],
                "expected_pattern": "Repeating"
            },
            {
                "name": "Strong Streak",
                "draws": [5, 6, 7, 8, 9, 5, 6, 7, 8, 9, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0],
                "expected_pattern": "Streak"
            },
            {
                "name": "Random Distribution",
                "draws": [3, 7, 2, 8, 1, 5, 4, 9, 6, 0, 2, 7, 3, 8, 5, 1, 4, 9, 6, 2],
                "expected_patterns": ["Mixed", "Alternating", "None"]
            }
        ]
        
        results: List[Dict[str, Any]] = []
        for test in test_cases:
            predictor = Predictor(test["draws"], "TEST")
            patterns = predictor.patterns["size_patterns"]
            
            detected = patterns["pattern_type"] or "None"
            strength = patterns["pattern_strength"]
            
            result: Dict[str, Any] = {
                "test_case": test["name"],
                "detected_pattern": detected,
                "pattern_strength": f"{strength:.0%}",
                "expected": test.get("expected_pattern") or test.get("expected_patterns"),
                "status": "PASS" if (detected == test.get("expected_pattern") or detected in test.get("expected_patterns", [])) else "FAIL"
            }
            results.append(result)
        
        for result in results:
            status = "✓" if result["status"] == "PASS" else "⚠"
            print(f"{status} {result['test_case']:30} → {result['detected_pattern']:15} ({result['pattern_strength']})")
        
        return results
    
    @staticmethod
    def test_probability_ranking() -> List[tuple[int, float, str, str]]:
        """Test probability ranking system."""
        from predictor import Predictor  # type: ignore
        from data_fetcher import create_sample_data  # type: ignore
        print("\n" + "="*60)
        print("TEST: Probability Ranking")
        print("="*60)

        draws = create_sample_data()
        predictor = Predictor(draws, "TEST")
        
        rankings = predictor.probability_engine.rank_all_numbers()
        
        print(f"\nAll numbers ranked by confidence:\n")
        for i, (num, score, size, color) in enumerate(rankings, 1):
            bar = "█" * int(score * 20)
            print(f"{i:2}. Number {num} | {bar:<20} {score:.2%} | {size:6} {color:8}")
        
        return rankings
    
    @staticmethod
    def test_size_color_mapping() -> Dict[str, Dict[int, str]]:
        """Test size and color mapping."""
        print("\n" + "="*60)
        print("TEST: Size & Color Mapping")
        print("="*60)
        
        from pattern_detector import SizeMapper, ColorMapper  # type: ignore
        
        print("\nNumber → Size Mapping:")
        for i in range(10):
            size = SizeMapper.get_size(i)
            print(f"  {i}: {size}")
        
        print("\nNumber → Color Mapping:")
        for i in range(10):
            color = ColorMapper.get_color(i)
            print(f"  {i}: {color}")
        
        return {
            "sizes": {i: SizeMapper.get_size(i) for i in range(10)},
            "colors": {i: ColorMapper.get_color(i) for i in range(10)}
        }
    
    @staticmethod
    def test_cycle_detection() -> List[tuple[str, List[int]]]:
        """Test cycle detection."""
        from predictor import Predictor  # type: ignore
        print("\n" + "="*60)
        print("TEST: Cycle Detection")
        print("="*60)

        # 2-round cycle
        cycle_2 = [3, 7, 3, 7, 3, 7, 3, 7, 3, 7, 3, 7, 3, 7, 3, 7, 3, 7, 3, 7]
        
        # 3-round cycle
        cycle_3 = [1, 5, 9, 1, 5, 9, 1, 5, 9, 1, 5, 9, 1, 5, 9, 1, 5, 9, 1, 5]
        
        # No cycle
        no_cycle = [3, 7, 2, 8, 1, 5, 4, 9, 6, 0, 2, 7, 3, 8, 5, 1, 4, 9, 6, 2]
        
        test_cases: List[tuple[str, List[int]]] = [
            ("2-Round Cycle", cycle_2),
            ("3-Round Cycle", cycle_3),
            ("No Cycle", no_cycle)
        ]
        
        for name, draws in test_cases:
            predictor = Predictor(draws, "TEST")
            cycles = predictor.patterns["cycles"]
            
            if cycles:
                detected = f"{cycles[0]['cycle_length']}-round (strength: {cycles[0]['strength']:.0%})"
            else:
                detected = "None"
            
            print(f"✓ {name:20} → {detected}")
        
        return test_cases
    
    @staticmethod
    def run_all_tests() -> None:
        """Run all tests."""
        print("\n" + "="*70)
        print(" "*15 + "BDG PREDICTION ENGINE - COMPREHENSIVE TEST SUITE")
        print("="*70)
        
        try:
            # Test 1: Size & Color Mapping
            TestSuite.test_size_color_mapping()
            
            # Test 2: Pattern Detection
            pattern_results = TestSuite.test_pattern_detection()
            
            # Test 3: Cycle Detection
            TestSuite.test_cycle_detection()
            
            # Test 4: Probability Ranking
            rankings = TestSuite.test_probability_ranking()
            
            # Test 5: Single Prediction
            prediction = TestSuite.test_single_prediction()

            failures = [result for result in pattern_results if result["status"] != "PASS"]
            if len(rankings) != 10:
                failures.append({"test_case": "Probability Ranking", "status": "FAIL"})
            if not isinstance(prediction, dict) or "primary_prediction" not in prediction:
                failures.append({"test_case": "Single Prediction", "status": "FAIL"})

            if failures:
                raise AssertionError(f"{len(failures)} test checks failed")
            
            print("\n" + "="*70)
            print("ALL TESTS COMPLETED SUCCESSFULLY ✓")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            logger.error(f"Test suite error: {e}", exc_info=True)


if __name__ == "__main__":
    # Run comprehensive tests
    TestSuite.run_all_tests()
