import logging
from typing import List, Dict, Tuple, Optional, Any, cast
from .pattern_detector import SizeMapper, ColorMapper
from .config import Config

logger = logging.getLogger(__name__)

class ProbabilityEngine:
    def __init__(self, draws: List[int], patterns: Dict[str, Any], weight_profile: Optional[Dict[str, float]] = None):
        self.draws = list(draws or [])
        self.patterns = patterns or {}
        self.weights = weight_profile or {
            "trend": Config.WEIGHT_TREND,
            "frequency": Config.WEIGHT_FREQUENCY,
            "cycle": Config.WEIGHT_CYCLE,
            "streak": Config.WEIGHT_STREAK,
            "sequence": Config.WEIGHT_SEQUENCE,
        }

    def calculate_confidence_score(self, number: int) -> float:
        score = 0.1
        # Hierarchical logic: Sequence (45%) + Patterns
        seq_scores = self.patterns.get("sequence_patterns", {}).get("scores", {})
        score = float(seq_scores.get(number, 0.1)) * 0.8 + 0.2 # Base + LSTM/Markov signal
        
        # Penalize immediate repeat
        if self.draws and number == self.draws[0]:
            score *= 0.72
            
        return min(score, 1.0)

    def rank_all_numbers(self) -> List[Tuple[int, float, str, str]]:
        rankings = []
        for num in range(10):
            score = self.calculate_confidence_score(num)
            rankings.append((num, score, SizeMapper.get_size(num), ColorMapper.get_color(num)))
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def get_top_predictions(self, n: int = 3) -> List[Dict[str, Any]]:
        ranked = self.rank_all_numbers()
        return [{"number": r[0], "prob": r[1], "size": r[2], "color": r[3]} for r in ranked[:n]]
