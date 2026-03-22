import logging
from typing import Any, List, Dict
from collections import Counter
from .config import Config

logger = logging.getLogger(__name__)

class SizeMapper:
    @staticmethod
    def get_size(number: int) -> str:
        return "Small" if number < 5 else "Big"
    
    @staticmethod
    def numbers_to_sizes(numbers: List[int]) -> List[str]:
        return [SizeMapper.get_size(n) for n in numbers]

class ColorMapper:
    COLOR_MAP = {0: "Red", 1: "Green", 2: "Red", 3: "Green", 4: "Red", 5: "Violet", 6: "Red", 7: "Green", 8: "Red", 9: "Green"}
    @staticmethod
    def get_color(number: int) -> str:
        return ColorMapper.COLOR_MAP.get(number, "Unknown")
    @staticmethod
    def numbers_to_colors(numbers: List[int]) -> List[str]:
        return [ColorMapper.get_color(n) for n in numbers]

class LLMSequenceAI:
    def __init__(self, recent_draws: List[int], max_context: int = Config.SEQUENCE_MAX_CONTEXT):
        self.draws = list(reversed(recent_draws[:Config.SEQUENCE_LOOKBACK_DRAWS]))
        self.max_context = max(1, min(max_context, 5))
        self.transitions = {order: {} for order in range(1, self.max_context + 1)}
        self.frequencies = Counter()
        self._train()

    def _train(self):
        for index, number in enumerate(self.draws):
            self.frequencies[number] += 1
            for order in range(1, self.max_context + 1):
                if index < order: continue
                context = tuple(self.draws[index - order:index])
                bucket = self.transitions[order].setdefault(context, Counter())
                bucket[number] += 1

    def predict_next(self, recent_context: List[int]) -> Dict[int, float]:
        scores = {i: 0.1 for i in range(10)}
        total_freq = sum(self.frequencies.values())
        if total_freq > 0:
            scores = {i: (self.frequencies.get(i, 0) + 1) / (total_freq + 10) for i in range(10)}
        
        ctx = [int(n) for n in recent_context[:self.max_context]]
        weights = {1: 0.20, 2: 0.30, 3: 0.50}
        for order in range(1, min(len(ctx), self.max_context) + 1):
            key = tuple(reversed(ctx[:order]))
            trans = self.transitions[order].get(key)
            if trans:
                t_total = sum(trans.values())
                w = weights.get(order, 0.5)
                for n, c in trans.items(): scores[n] += (c / t_total) * w
        
        total = sum(scores.values()) or 1.0
        return {n: s / total for n, s in scores.items()}

class PatternDetector:
    def __init__(self, draws: List[int]):
        self.draws = draws
        self.sizes = SizeMapper.numbers_to_sizes(draws)
        self.colors = ColorMapper.numbers_to_colors(draws)

    def analyze_all_patterns(self) -> Dict[str, Any]:
        # Minimal version for execution speed, keeping core logic
        try:
            from .sequence_model import get_global_model
            deep = get_global_model()
            seq = deep.get_summary(self.draws[:20]) if deep.is_ready else LLMSequenceAI(self.draws).get_model_summary(self.draws[:3])
        except:
            seq = LLMSequenceAI(self.draws).get_model_summary(self.draws[:3])
            
        return {
            "size_patterns": self._detect_size(),
            "color_patterns": {"dominant_color": self._get_dominant_color()},
            "sequence_patterns": seq,
            "number_frequency": Counter(self.draws)
        }

    def _detect_size(self):
        recent = self.sizes[:5]
        return {"current_streak": {"length": len([x for x in recent if x == recent[0]]), "type": recent[0]}}

    def _get_dominant_color(self):
        c = Counter(self.colors)
        top = c.most_common(1)[0] if c else (None, 0)
        return {"color": top[0], "percentage": (top[1]/len(self.colors))*100 if self.colors else 0}
