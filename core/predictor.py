import logging
from typing import Any, Dict, List, Optional
from .pattern_detector import PatternDetector
from .probability_engine import ProbabilityEngine
from .config import Config

logger = logging.getLogger(__name__)

class Predictor:
    def __init__(self, draws: List[int], period: Optional[str] = None):
        self.draws = draws
        self.period = period
        self.detector = PatternDetector(draws)
        self.patterns = self.detector.analyze_all_patterns()
        self.engine = ProbabilityEngine(draws, self.patterns)

    def generate_prediction(self) -> Dict[str, Any]:
        top3 = self.engine.get_top_predictions(3)
        return {
            "status": "ok",
            "period": self.period,
            "top3": top3,
            "model": self.patterns.get("sequence_patterns", {}).get("source", "unknown")
        }
