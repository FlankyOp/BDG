"""
Usage Examples — demonstrate different ways to use the prediction engine.

Run a specific example:
    python examples.py          # shows the menu
    python examples.py 1        # runs Example 1 directly
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from predictor import Predictor
from data_fetcher import DataFetcher, create_sample_data
from pattern_detector import PatternDetector
from probability_engine import ProbabilityEngine
from main import PredictionEngine


# ==================================================
# EXAMPLE 1: Basic Single Prediction
# ==================================================

def example_1_basic_prediction():
    """Basic single prediction using sample draws."""
    draws = create_sample_data()
    predictor = Predictor(draws, period="20260317100011227")
    predictor.print_prediction()

    quick_pred = predictor.get_quick_prediction()
    print(f"\nQuick Access:")
    print(f"  Best Number: {quick_pred['best_number']}")
    print(f"  Confidence:  {quick_pred['confidence']}")
    print(f"  Color:       {quick_pred['best_color']}")
    print(f"  Size:        {quick_pred['best_size']}")


# ==================================================
# EXAMPLE 2: Run Full Prediction Engine (sample mode)
# ==================================================

def example_2_engine_single():
    """Run PredictionEngine in sample-data mode for one prediction."""
    engine = PredictionEngine(use_sample_data=True)
    engine.run_single_prediction()


# ==================================================
# EXAMPLE 3: Continuous Polling (3 runs to avoid infinite loop)
# ==================================================

def example_3_continuous_polling():
    """Continuous polling with a 10-second interval, capped at 3 runs."""
    engine = PredictionEngine(use_sample_data=False)
    print("Starting continuous polling (3 runs, 10 s interval)…")
    print("Press Ctrl+C to stop early.\n")
    engine.run_continuous_polling(interval_seconds=10, max_runs=3)


# ==================================================
# EXAMPLE 4: Advanced Pattern Analysis
# ==================================================

def example_4_pattern_analysis():
    """Detailed pattern analysis of sample draws."""
    draws = create_sample_data()
    detector = PatternDetector(draws)
    patterns = detector.analyze_all_patterns()

    size_patterns  = patterns["size_patterns"]
    cycles         = patterns["cycles"]

    print(f"Size Pattern Type: {size_patterns['pattern_type']}")
    print(f"Pattern Strength:  {size_patterns['pattern_strength']:.0%}")
    print(f"\nDetected Cycles: {len(cycles)}")
    for cycle in cycles:
        print(f"  - {cycle['cycle_length']}-round cycle (strength: {cycle['strength']:.0%})")


# ==================================================
# EXAMPLE 5: Custom Probability Scoring
# ==================================================

def example_5_probability_scoring():
    """Per-number confidence scores and a detailed explanation."""
    draws   = create_sample_data()
    detector = PatternDetector(draws)
    patterns = detector.analyze_all_patterns()
    engine   = ProbabilityEngine(draws, patterns)

    for number in range(10):
        confidence = engine.calculate_confidence_score(number)
        print(f"Number {number}: {confidence:.2%} confidence")

    explanation = engine.explain_prediction(7)
    print(f"\nDetailed explanation for Number 7:")
    for factor, value in explanation.items():
        print(f"  {factor}: {value}")


# ==================================================
# EXAMPLE 6: Batch Predictions
# ==================================================

def example_6_batch_predictions():
    """Run 5 predictions and save results to JSON."""
    predictions: List[Dict[str, Any]] = []
    for round_num in range(5):
        draws     = create_sample_data()
        predictor = Predictor(draws, period=f"20260317100011{220 + round_num}")
        quick     = predictor.get_quick_prediction()
        quick["round"] = round_num + 1
        predictions.append(quick)

    with open("batch_predictions.json", "w") as f:
        json.dump(predictions, f, indent=2)
    print("Saved 5 predictions to batch_predictions.json")


# ==================================================
# EXAMPLE 7: API-Based Prediction with Error Handling
# ==================================================

def example_7_api_prediction():
    """Try to fetch real data; fall back to sample data on error."""
    fetcher = DataFetcher()
    period  = "20260317100011227"
    data    = fetcher.fetch_past_draws(period)

    if data:
        draws = fetcher.extract_draws(data)
        if draws:
            numbers   = [int(d["number"]) for d in draws[:500]]
            predictor = Predictor(numbers, period)
            predictor.print_prediction()
        else:
            print("Failed to extract draws")
    else:
        print("Failed to fetch data from API")


# ==================================================
# EXAMPLE 8: Export and Analyze Results
# ==================================================

def example_8_export():
    """Run 3 predictions then export them to JSON."""
    engine = PredictionEngine(use_sample_data=True)
    for _ in range(3):
        engine.run_single_prediction()
    engine.analyze_recent_predictions(num_predictions=3)
    engine.export_predictions("my_predictions.json")


# ==================================================
# EXAMPLE 9: Integration with External Systems
# ==================================================

def example_9_external_integration():
    """Send a prediction payload to an external API (stub)."""
    def send_prediction_to_api(prediction: Dict[str, Any]) -> bool:
        payload: Dict[str, Any] = {
            "number":     prediction["best_number"],
            "size":       prediction["best_size"],
            "color":      prediction["best_color"],
            "confidence": prediction["confidence"],
            "period":     prediction["next_period"],
        }
        # Uncomment to send for real:
        # import requests
        # response = requests.post("https://your-api.com/predictions", json=payload)
        # return response.status_code == 200
        print(f"  Payload ready: {payload}")
        return True

    draws     = create_sample_data()
    predictor = Predictor(draws, "20260317100011227")
    quick     = predictor.get_quick_prediction()
    success   = send_prediction_to_api(quick)
    print(f"Prediction sent: {'✓' if success else '✗'}")


# ==================================================
# EXAMPLE 10: File-Based Database Integration
# ==================================================

def example_10_database():
    """Persist predictions to a simple JSON file-database."""

    class PredictionDatabase:
        def __init__(self, db_file: str = "predictions.db.json"):
            self.db_file = db_file
            self.data: List[Dict[str, Any]] = []
            self.load()

        def load(self) -> None:
            if Path(self.db_file).exists():
                with open(self.db_file) as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        loaded_list = cast(List[Any], loaded)
                        self.data = [cast(Dict[str, Any], d) for d in loaded_list if isinstance(d, dict)]

        def save(self) -> None:
            with open(self.db_file, "w") as f:
                json.dump(self.data, f, indent=2)

        def add_prediction(self, prediction: Dict[str, Any]) -> None:
            self.data.append(prediction)
            self.save()

        def get_by_period(self, period: str) -> Optional[Dict[str, Any]]:
            return next(
                (p for p in self.data if p.get("next_period") == period), None
            )

    db        = PredictionDatabase()
    draws     = create_sample_data()
    predictor = Predictor(draws, "20260317100011227")
    prediction = predictor.print_prediction()
    db.add_prediction(prediction)
    print("Saved prediction to database")


# ==================================================
# EXAMPLE 11: Real-time Web Dashboard Data
# ==================================================

def example_11_dashboard_data():
    """Generate a JSON-serialisable snapshot for a live dashboard."""
    draws     = create_sample_data()
    predictor = Predictor(draws, "20260317100011227")
    prediction = predictor.generate_prediction()

    dashboard_data: Dict[str, Any] = {
        "timestamp":    prediction["timestamp"],
        "next_period":  prediction["next_period"],
        "predictions": [
            prediction["primary_prediction"],
            prediction["alternative_prediction"],
            prediction["strong_possibility"],
        ],
        "trends":   prediction["trend_analysis"],
        "summary":  prediction["summary"],
    }
    print(json.dumps(dashboard_data, indent=2))


# ==================================================
# EXAMPLE 12: Performance Benchmarking
# ==================================================

def example_12_benchmark():
    """Time 100 prediction cycles to gauge throughput."""
    draws = create_sample_data()
    start = time.time()

    for i in range(100):
        predictor  = Predictor(draws, f"20260317100011{227 + i}")
        predictor.generate_prediction()

    elapsed = time.time() - start
    print(f"100 predictions in {elapsed:.2f}s")
    print(f"Average: {elapsed / 100 * 1000:.2f} ms per prediction")


# ==================================================
# MENU / ENTRY POINT
# ==================================================

EXAMPLES = {
    "1":  ("Basic Single Prediction",              example_1_basic_prediction),
    "2":  ("Full Engine (sample mode)",             example_2_engine_single),
    "3":  ("Continuous Polling (3 runs)",           example_3_continuous_polling),
    "4":  ("Advanced Pattern Analysis",             example_4_pattern_analysis),
    "5":  ("Custom Probability Scoring",            example_5_probability_scoring),
    "6":  ("Batch Predictions → JSON",              example_6_batch_predictions),
    "7":  ("API-Based Prediction w/ Error Handling",example_7_api_prediction),
    "8":  ("Export & Analyze Results",              example_8_export),
    "9":  ("External Integration (stub)",           example_9_external_integration),
    "10": ("File-Based Database",                   example_10_database),
    "11": ("Dashboard Snapshot",                    example_11_dashboard_data),
    "12": ("Performance Benchmark",                 example_12_benchmark),
}


def print_menu():
    print("\n" + "=" * 55)
    print("   BDG PREDICTION ENGINE — USAGE EXAMPLES")
    print("=" * 55)
    for key, (label, _) in EXAMPLES.items():
        print(f"  {key:>2}. {label}")
    print("   0. Exit")
    print("=" * 55)


if __name__ == "__main__":
    # Allow `python examples.py <number>` for CI / quick runs
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in EXAMPLES:
            print(f"\nRunning Example {choice}: {EXAMPLES[choice][0]}\n")
            EXAMPLES[choice][1]()
        else:
            print(f"Unknown example '{choice}'. Valid: {', '.join(EXAMPLES.keys())}")
        sys.exit(0)

    # Interactive menu
    while True:
        print_menu()
        choice = input("Select example (0 to exit): ").strip()
        if choice == "0":
            print("Exiting examples.")
            break
        if choice in EXAMPLES:
            print(f"\nRunning Example {choice}: {EXAMPLES[choice][0]}\n")
            try:
                EXAMPLES[choice][1]()
            except KeyboardInterrupt:
                print("\n[Interrupted]")
        else:
            print("Invalid selection. Please try again.")
