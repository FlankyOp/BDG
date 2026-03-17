"""
Main Module
Entry point for the BDG Game Prediction Engine.
Handles CLI, continuous polling, and result logging.
"""

import logging
import time
import json
import os
from typing import Any, Dict, Optional, List, cast
from datetime import datetime
from data_fetcher import DataFetcher, create_sample_data
from predictor import Predictor
from config import Config
import firebase_client

# Configure logging
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, f"bdg_predictor_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class PredictionEngine:
    """Main prediction engine controller."""
    
    def __init__(self, use_sample_data: bool = False):
        """
        Initialize prediction engine.
        
        Args:
            use_sample_data: If True, use sample data instead of API
        """
        self.data_fetcher = DataFetcher()
        self.use_sample_data = use_sample_data
        self.prediction_history: List[Dict[str, Any]] = []
        self.results_file = os.path.join(LOG_DIR, f"predictions_{datetime.now().strftime('%Y%m%d')}.json")
        self.learning_file = os.path.join(LOG_DIR, "adaptive_weights.json")
        self.learning_profile = self._load_learning_profile()
        self.pending_feedback: Optional[Dict[str, Any]] = None
        self.pending_status_eval: Optional[Dict[str, Any]] = None

    @staticmethod
    def _number_to_color(number: int) -> str:
        if number == 5:
            return "Violet"
        if number in (1, 3, 7, 9):
            return "Green"
        return "Red"

    @staticmethod
    def _number_to_size(number: int) -> str:
        return "Big" if number >= 5 else "Small"

    @staticmethod
    def _color_tokens(color_value: Any) -> List[str]:
        raw = str(color_value or "").replace("|", ",").replace("/", ",")
        parts = [p.strip().title() for p in raw.split(",") if p.strip()]
        return parts if parts else ["Red"]

    def _evaluate_pending_status(
        self,
        actual_number: int,
        actual_period: str,
        actual_color_value: Any,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate previous prediction candidates against the latest actual draw."""
        if not self.pending_status_eval:
            return None

        payload = self.pending_status_eval
        predicted = cast(Dict[str, Dict[str, Any]], payload["predicted"]) 
        primary = predicted.get("primary", {})
        predicted_number = int(primary.get("number", 0))
        predicted_color = str(primary.get("color", "Red"))
        predicted_size = str(primary.get("size", "Small"))

        color_tokens = self._color_tokens(actual_color_value)
        actual_color = color_tokens[0]
        actual_size = self._number_to_size(actual_number)

        candidate_status: Dict[str, Dict[str, str]] = {}
        for label, candidate in predicted.items():
            c_num = int(candidate.get("number", -1))
            c_color = str(candidate.get("color", "Red"))
            c_size = str(candidate.get("size", "Small"))
            candidate_status[label] = {
                "number": "HIT" if c_num == actual_number else "MISS",
                "color": "HIT" if c_color in color_tokens else "MISS",
                "size": "HIT" if c_size == actual_size else "MISS",
            }

        evaluation = {
            "target_period": payload.get("target_period"),
            "actual_period": actual_period,
            "predicted": predicted,
            "actual": {
                "number": actual_number,
                "color": actual_color,
                "color_tokens": color_tokens,
                "size": actual_size,
            },
            "status": {
                "number": "HIT" if predicted_number == actual_number else "MISS",
                "color": "HIT" if predicted_color in color_tokens else "MISS",
                "size": "HIT" if predicted_size == actual_size else "MISS",
            },
            "candidates": candidate_status,
            "evaluated_at": datetime.now().isoformat(),
        }

        self.pending_status_eval = None
        return evaluation
    
    # ==================== DATA RETRIEVAL ====================
    
    def fetch_latest_draws(self, period: str) -> Optional[List[int]]:
        """
        Fetch latest game draws.
        
        Args:
            period: Game period ID
            
        Returns:
            List of latest draw numbers or None on error
        """
        if self.use_sample_data:
            logger.info("Using sample data (API disabled)")
            return create_sample_data()
        
        try:
            data = self.data_fetcher.fetch_past_draws(period)
            if not data:
                logger.warning("Failed to fetch data from API, using sample data")
                return create_sample_data()

            draws = self.data_fetcher.extract_draws(data)
            if not draws:
                logger.warning("No draws extracted, using sample data")
                return create_sample_data()

            # Sort by period descending and extract numbers directly from the
            # already-fetched draws — avoids a redundant second API call that
            # get_latest_draws() would otherwise trigger internally.
            try:
                draws.sort(
                    key=lambda x: int(str(x["period"]).replace("-", "")),
                    reverse=True
                )
            except (ValueError, TypeError):
                pass
            numbers = [int(d["number"]) for d in draws[:Config.HISTORY_DRAWS_LIMIT]]
            return numbers if numbers else create_sample_data()
            
        except Exception as e:
            logger.error(f"Error fetching draws: {e}")
            return create_sample_data()
    
    def run_single_prediction(self, period: Optional[str] = None) -> Optional[Dict[str, Any]]:

        if period is None:
            # Fetch the latest draw to get the current period
            latest_draws_data = self.data_fetcher.fetch_past_draws()
            if not latest_draws_data:
                logger.error("Could not fetch latest draws data.")
                return None
            
            latest_draws = self.data_fetcher.extract_draws(latest_draws_data)
            if not latest_draws:
                logger.error("Could not extract latest draws.")
                return None

            period = latest_draws[0]["period"]
            logger.info(f"Using latest period from API: {period}")
        """
        Run a single prediction.
        
        Args:
            period: Game period (auto-detected if None)
            
        Returns:
            Prediction result dictionary
        """
        logger.info("Generating single prediction...")

        # Fetch the latest draw to get the current period
        latest_draws_data = self.data_fetcher.fetch_past_draws()
        if not latest_draws_data:
            logger.error("Could not fetch latest draws data.")
            return None
        
        latest_draws = self.data_fetcher.extract_draws(latest_draws_data)
        if not latest_draws:
            logger.error("Could not extract latest draws.")
            return None

        period_str = latest_draws[0]["period"]
        if period_str is None:
            logger.error("Could not extract period from latest draws.")
            return None
        logger.info(f"Using latest period from API: {period_str}")
        
        # Fetch draws
        draws = self.fetch_latest_draws(period_str)
        if not draws or len(draws) < 10:
            logger.error("Insufficient draw data")
            return None

        current_game_code = "WinGo_1M"

        # Evaluate previous prediction against the latest completed draw.
        hit_miss_status = self._evaluate_pending_status(
            actual_number=draws[0],
            actual_period=str(period_str),
            actual_color_value=latest_draws[0].get("color"),
        )
        if hit_miss_status:
            firebase_client.push_hit_miss_status(current_game_code, hit_miss_status)
            logger.info(
                "Hit/Miss | Number: %s | Color: %s | Size: %s",
                hit_miss_status["status"]["number"],
                hit_miss_status["status"]["color"],
                hit_miss_status["status"]["size"],
            )

        # Use the most recent completed number as feedback for the previous prediction.
        if Config.ENABLE_SELF_LEARNING:
            self._apply_feedback(actual_number=draws[0])
        
        # Generate prediction
        predictor = Predictor(draws, period_str, weight_profile=self.learning_profile)
        prediction = predictor.generate_prediction()
        print(predictor.format_output(prediction))

        self._capture_pending_feedback(predictor, prediction)
        alternative = prediction.get("alternative_prediction") or prediction["primary_prediction"]
        backup = prediction.get("strong_possibility") or alternative
        self.pending_status_eval = {
            "target_period": prediction.get("next_period"),
            "predicted": {
                "primary": {
                    "number": int(prediction["primary_prediction"]["number"]),
                    "color": str(prediction["primary_prediction"]["color"]),
                    "size": str(prediction["primary_prediction"]["size"]),
                },
                "alternative": {
                    "number": int(alternative["number"]),
                    "color": str(alternative["color"]),
                    "size": str(alternative["size"]),
                },
                "backup": {
                    "number": int(backup["number"]),
                    "color": str(backup["color"]),
                    "size": str(backup["size"]),
                },
            },
            "created_at": prediction.get("timestamp"),
        }
        
        self.prediction_history.append(prediction)
        self._save_prediction(prediction)
        
        # Determine current game config to match front-end
        # Here we just default to WinGo_1M, but ideally we'd pass it in if it's dynamic
        # Push state and prediction to Firebase
        firebase_client.push_game_state(
            current_game_code, 
            live_data={"current": {"issueNumber": period_str, "endTime": int(time.time() * 1000) + 60000}, "next": {"issueNumber": prediction["next_period"]}}, 
            history_data=self._get_recent_history(period_str)
        )
        firebase_client.push_prediction(current_game_code, prediction)
        
        return prediction

    # ==================== SELF LEARNING ====================

    def _default_weights(self) -> Dict[str, float]:
        return {
            "trend": Config.WEIGHT_TREND,
            "frequency": Config.WEIGHT_FREQUENCY,
            "cycle": Config.WEIGHT_CYCLE,
            "streak": Config.WEIGHT_STREAK,
            "noise": Config.WEIGHT_NOISE,
        }

    def _normalize_weights(self, profile: Dict[str, float]) -> Dict[str, float]:
        floor = Config.MIN_WEIGHT_FLOOR
        adjusted = {k: max(float(v), floor) for k, v in profile.items()}
        total = sum(adjusted.values()) or 1.0
        return {k: v / total for k, v in adjusted.items()}

    def _load_learning_profile(self) -> Dict[str, float]:
        defaults = self._default_weights()
        if not os.path.exists(self.learning_file):
            return self._normalize_weights(defaults)

        try:
            with open(self.learning_file, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data_dict = cast(Dict[str, Any], data)
                parsed: Dict[str, float] = {}
                for k, v in data_dict.items():
                    if k in defaults:
                        try:
                            parsed[k] = float(v)
                        except (TypeError, ValueError):
                            continue
                merged = {**defaults, **parsed}
                return self._normalize_weights(merged)
        except Exception as e:
            logger.warning(f"Failed to load adaptive weights: {e}")

        return self._normalize_weights(defaults)

    def _save_learning_profile(self) -> None:
        try:
            with open(self.learning_file, "w") as f:
                json.dump(self.learning_profile, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save adaptive weights: {e}")

    def _capture_pending_feedback(self, predictor: Predictor, prediction: Dict[str, Any]) -> None:
        primary = int(prediction["primary_prediction"]["number"])
        alt = int(prediction["alternative_prediction"]["number"]) if prediction.get("alternative_prediction") else primary
        backup = int(prediction["strong_possibility"]["number"]) if prediction.get("strong_possibility") else alt

        self.pending_feedback = {
            "primary": primary,
            "alternative": alt,
            "backup": backup,
            "components": {
                primary: predictor.probability_engine.get_weight_components(primary),
                alt: predictor.probability_engine.get_weight_components(alt),
                backup: predictor.probability_engine.get_weight_components(backup),
            },
        }

    def _apply_feedback(self, actual_number: int) -> None:
        if not self.pending_feedback:
            return

        learning_rate = Config.LEARNING_RATE
        payload = self.pending_feedback
        primary = payload["primary"]
        alternative = payload["alternative"]
        backup = payload["backup"]
        components: Dict[int, Dict[str, float]] = payload["components"]

        signals: Dict[int, float] = {
            primary: -0.5,
            alternative: 0.0,
            backup: 0.0,
        }
        if actual_number == primary:
            signals[primary] = 1.0
        elif actual_number == alternative:
            signals[alternative] = 0.5
        elif actual_number == backup:
            signals[backup] = 0.25

        updated = dict(self.learning_profile)
        for number, signal in signals.items():
            comp = components.get(number, {})
            for factor, value in comp.items():
                if factor in updated:
                    updated[factor] = updated[factor] + learning_rate * signal * float(value)

        self.learning_profile = self._normalize_weights(updated)
        self._save_learning_profile()
        self.pending_feedback = None
    
    def run_continuous_polling(self, interval_seconds: int = 30, max_runs: Optional[int] = None) -> None:
        """
        Run continuous polling mode (check for updates every N seconds).
        
        Args:
            interval_seconds: Seconds between polls (default: 30)
            max_runs: Maximum number of runs (None = infinite)
        """
        logger.info(f"Starting continuous polling (interval: {interval_seconds}s)")
        
        run_count = 0
        
        try:
            while True:
                if max_runs and run_count >= max_runs:
                    logger.info(f"Reached max runs ({max_runs})")
                    break
                
                run_count += 1
                logger.info(f"Poll #{run_count} - {datetime.now()}")
                
                # Run prediction
                period = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{str(run_count).zfill(4)}"
                self.run_single_prediction(period)
                
                # Log summary
                logger.info(f"Waiting {interval_seconds} seconds for next poll...")
                print(f"\n[POLLING] Next check in {interval_seconds} seconds... (Ctrl+C to stop)\n")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Polling interrupted by user")
            print("\n[STOPPED] Polling halted by user")
        except Exception as e:
            logger.error(f"Error during polling: {e}")
        
        self._print_session_summary()
    
    # ==================== RESULT LOGGING ====================
    
    def _save_prediction(self, prediction: Dict[str, Any]) -> None:
        """Save prediction to JSON file."""
        try:
            # Load existing predictions
            existing: List[Dict[str, Any]] = []
            if os.path.exists(self.results_file):
                with open(self.results_file, 'r') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        existing = cast(List[Dict[str, Any]], loaded)
            
            # Append new prediction
            existing.append(prediction)
            
            # Save
            with open(self.results_file, 'w') as f:
                json.dump(existing, f, indent=2)
            
            logger.info(f"Prediction saved to {self.results_file}")
            
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
    
    def _get_recent_history(self, period: Optional[str]) -> List[Dict[str, Any]]:
        """Safely get recent history draws, handling None cases."""
        if period is None:
            logger.warning("No period for _get_recent_history")
            return []
        data = self.data_fetcher.fetch_past_draws(period)
        return self.data_fetcher.extract_draws(data) if data is not None else []

    def _print_session_summary(self) -> None:
        """Print summary of polling session."""
        if not self.prediction_history:
            return
        
        print("\n" + "="*60)
        print("         POLLING SESSION SUMMARY")
        print("="*60)
        print(f"Total predictions: {len(self.prediction_history)}")
        print(f"Session duration: {datetime.now()}")
        print(f"Results file: {self.results_file}")
        print("="*60 + "\n")
    
    # ==================== ANALYSIS TOOLS ====================
    
    def analyze_recent_predictions(self, num_predictions: int = 5) -> None:
        """
        Analyze recent predictions for patterns.
        
        Args:
            num_predictions: Number of recent predictions to analyze
        """
        if not self.prediction_history:
            logger.warning("No prediction history available")
            return
        
        recent = self.prediction_history[-num_predictions:]
        
        print("\n" + "="*60)
        print("         RECENT PREDICTIONS ANALYSIS")
        print("="*60 + "\n")
        
        for i, pred in enumerate(recent, 1):
            primary = pred["primary_prediction"]
            print(f"Prediction #{i}")
            print(f"  Best Number: {primary['number']} ({primary['color']}, {primary['size']})")
            print(f"  Confidence: {primary['accuracy']}")
            print()
    
    def export_predictions(self, filename: Optional[str] = None) -> None:
        """
        Export predictions to CSV or JSON.
        
        Args:
            filename: Export filename (defaults to auto-generated)
        """
        if not filename:
            filename = f"bdg_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.prediction_history, f, indent=2)
            
            logger.info(f"Predictions exported to {filename}")
            print(f"\nPredictions exported to: {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting predictions: {e}")


def print_menu() -> None:
    """Print main menu."""
    print("\n" + "="*60)
    print("    BDG GAME PREDICTION ENGINE - MAIN MENU")
    print("="*60)
    print("1. Single Prediction")
    print("2. Continuous Polling (30 seconds interval)")
    print("3. Continuous Polling (Custom interval)")
    print("4. View Recent Predictions")
    print("5. Export Predictions")
    print("6. Exit")
    print("="*60)


def main():
    """Main entry point."""
    logger.info("BDG Game Prediction Engine started")
    print("\n" + "="*60)
    print("    BDG GAME PREDICTION ENGINE")
    print("    Automatic Pattern Analysis & Prediction System")
    print("="*60 + "\n")
    
    # Check for command line arguments
    import sys
    
    use_sample = "--sample" in sys.argv or "-s" in sys.argv
    continuous = "--continuous" in sys.argv or "-c" in sys.argv
    interval  = 30
    max_runs: Optional[int] = None

    # Parse --interval=N and --max-runs=N
    for arg in sys.argv:
        if arg.startswith("--interval="):
            try:
                interval = int(arg.split("=")[1])
            except ValueError:
                logger.warning("Invalid interval, using default 30s")
        elif arg.startswith("--max-runs="):
            try:
                max_runs = int(arg.split("=")[1])
            except ValueError:
                logger.warning("Invalid max-runs value, running indefinitely")

    engine = PredictionEngine(use_sample_data=use_sample)

    # Quick mode options
    if continuous:
        engine.run_continuous_polling(interval_seconds=interval, max_runs=max_runs)
        return
    
    # Interactive menu
    while True:
        print_menu()
        choice = input("Select option (1-6): ").strip()
        
        if choice == "1":
            print("\nGenerating single prediction...")
            engine.run_single_prediction()
        
        elif choice == "2":
            print("\nStarting continuous polling (30s interval)...")
            print("Press Ctrl+C to stop.\n")
            engine.run_continuous_polling(interval_seconds=30, max_runs=None)
        
        elif choice == "3":
            try:
                custom_interval = int(input("Enter interval in seconds: ").strip())
                print(f"\nStarting continuous polling ({custom_interval}s interval)...")
                print("Press Ctrl+C to stop.\n")
                engine.run_continuous_polling(interval_seconds=custom_interval, max_runs=None)
            except ValueError:
                print("Invalid interval. Using default 30 seconds.")
                engine.run_continuous_polling(interval_seconds=30, max_runs=None)
        
        elif choice == "4":
            print("\nRecent predictions:")
            engine.analyze_recent_predictions(num_predictions=5)
        
        elif choice == "5":
            filename = input("Enter export filename (press Enter for auto): ").strip()
            if not filename:
                filename = None
            engine.export_predictions(filename)
        
        elif choice == "6":
            print("\nExiting...")
            logger.info("Application closed by user")
            break
        
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
