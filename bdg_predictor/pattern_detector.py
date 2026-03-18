"""
Pattern Detector Module
Analyzes game patterns for size, color, streaks, and cycles.
"""

import logging
from typing import Any, List, Dict
from collections import Counter
from config import Config

logger = logging.getLogger(__name__)


class SizeMapper:
    """Maps numbers to sizes."""
    
    @staticmethod
    def get_size(number: int) -> str:
        """
        Determine size from number.
        0-4: Small, 5-9: Big
        """
        return "Small" if number < 5 else "Big"
    
    @staticmethod
    def numbers_to_sizes(numbers: List[int]) -> List[str]:
        """Convert list of numbers to sizes."""
        return [SizeMapper.get_size(n) for n in numbers]


class ColorMapper:
    """Maps numbers to colors."""
    
    COLOR_MAP = {
        0: "Red",      # 0: Red/Violet (use Red)
        1: "Green",    # 1: Green
        2: "Red",      # 2: Red
        3: "Green",    # 3: Green
        4: "Red",      # 4: Red
        5: "Violet",   # 5: Green/Violet (use Violet)
        6: "Red",      # 6: Red
        7: "Green",    # 7: Green
        8: "Red",      # 8: Red
        9: "Green"     # 9: Green
    }
    
    @staticmethod
    def get_color(number: int) -> str:
        """Get color for a number."""
        return ColorMapper.COLOR_MAP.get(number, "Unknown")
    
    @staticmethod
    def numbers_to_colors(numbers: List[int]) -> List[str]:
        """Convert list of numbers to colors."""
        return [ColorMapper.get_color(n) for n in numbers]


class LLMSequenceAI:
    """Deterministic token-style sequence learner trained on recent draw history.

    This is not a true large language model. It applies the same next-token idea
    to draw numbers by learning 1-gram to N-gram transitions from the last API
    history window and then blending those sequence signals with a global prior.
    """

    def __init__(self, recent_draws: List[int], max_context: int = Config.SEQUENCE_MAX_CONTEXT):
        self.draws = list(reversed(recent_draws[:Config.SEQUENCE_LOOKBACK_DRAWS]))
        self.max_context = max(1, min(max_context, 5))
        self.transitions: Dict[int, Dict[tuple[int, ...], Counter[int]]] = {
            order: {} for order in range(1, self.max_context + 1)
        }
        self.frequencies: Counter[int] = Counter()
        self._train()

    def _train(self) -> None:
        """Train the sequence model on chronological draws."""
        for index, number in enumerate(self.draws):
            self.frequencies[number] += 1
            for order in range(1, self.max_context + 1):
                if index < order:
                    continue

                context = tuple(self.draws[index - order:index])
                bucket = self.transitions[order].setdefault(context, Counter())
                bucket[number] += 1

    def _base_distribution(self) -> Dict[int, float]:
        total = sum(self.frequencies.values())
        if total <= 0:
            return {number: 0.1 for number in range(10)}

        # Laplace smoothing prevents zero-probability dead ends.
        denominator = total + 10
        return {
            number: (self.frequencies.get(number, 0) + 1) / denominator
            for number in range(10)
        }

    def predict_next(self, recent_context: List[int]) -> Dict[int, float]:
        """Return normalized next-number probabilities for the newest-first context."""
        scores = self._base_distribution()
        if not recent_context:
            return scores

        normalized_context = [int(number) for number in recent_context[:self.max_context]]
        weight_plan = {
            1: 0.20,
            2: 0.30,
            3: 0.50,
            4: 0.60,
            5: 0.70,
        }

        for order in range(1, min(len(normalized_context), self.max_context) + 1):
            context = tuple(reversed(normalized_context[:order]))
            transitions = self.transitions[order].get(context)
            if not transitions:
                continue

            total = sum(transitions.values())
            if total <= 0:
                continue

            blend_weight = weight_plan.get(order, 0.50)
            for number, count in transitions.items():
                scores[number] += (count / total) * blend_weight

        # Penalize immediate repeats unless the last 3 draws form a streak.
        if normalized_context:
            latest = normalized_context[0]
            is_short_streak = len(normalized_context) >= 3 and len(set(normalized_context[:3])) == 1
            if not is_short_streak:
                scores[latest] *= 0.72

        total_score = sum(scores.values()) or 1.0
        return {number: score / total_score for number, score in scores.items()}

    def get_model_summary(self, recent_context: List[int]) -> Dict[str, Any]:
        """Return sequence diagnostics useful for downstream scoring and logging."""
        probabilities = self.predict_next(recent_context)
        ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)

        return {
            "scores": {number: probabilities.get(number, 0.0) for number in range(10)},
            "top_prediction": ranked[0][0] if ranked else None,
            "top_confidence": ranked[0][1] if ranked else 0.0,
            "context": recent_context[:self.max_context],
            "trained_draws": len(self.draws),
            "max_context": self.max_context,
        }


class PatternDetector:
    """Detects patterns in game results."""
    
    def __init__(self, draws: List[int]):
        """
        Initialize pattern detector.
        
        Args:
            draws: List of recent draw numbers (up to 500)
        """
        # Draws are expected newest-first from API/main polling.
        self.draws = draws
        self.sizes = SizeMapper.numbers_to_sizes(draws)
        self.colors = ColorMapper.numbers_to_colors(draws)
    
    # ==================== SIZE PATTERNS ====================
    
    def detect_size_pattern(self) -> Dict[str, Any]:
        """
        Detect size patterns: alternating, repeating, streaks, mixed.
        
        Returns:
            Dictionary with detected patterns
        """
        patterns: Dict[str, Any] = {
            "alternating": self._detect_alternating_pattern(),
            "repeating": self._detect_repeating_pattern(),
            "current_streak": self._detect_current_streak(),
            "streak_history": self._detect_streak_history(),
            "pattern_type": None,
            "pattern_strength": 0.0
        }
        
        # Determine strongest pattern
        if patterns["alternating"]["found"]:
            patterns["pattern_type"] = "Alternating"
            patterns["pattern_strength"] = patterns["alternating"]["strength"]
        elif patterns["repeating"]["found"]:
            patterns["pattern_type"] = "Repeating"
            patterns["pattern_strength"] = patterns["repeating"]["strength"]
        elif patterns["current_streak"]["length"] >= 3:
            patterns["pattern_type"] = "Streak"
            patterns["pattern_strength"] = min(0.9, patterns["current_streak"]["length"] / 5)
        
        return patterns
    
    def _detect_alternating_pattern(self) -> Dict[str, Any]:
        """
        Detect alternating B/S or S/B pattern with robust validation.
        Uses extended window and calibrated strength to reduce weak-signal overfitting.
        """
        if len(self.sizes) < 4:
            return {"found": False, "strength": 0.0, "details": "Insufficient data"}
        
        # Widen to last 15 draws; require ≥90% alternating transitions
        recent = list(reversed(self.sizes[:15]))
        alt_count = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        ratio = alt_count / max(len(recent) - 1, 1)

        if ratio >= 0.90:
            # Calibrated strength: very high ratio merits high confidence
            calibrated_strength = 0.78 + ratio * 0.15  # Range: 0.78-0.93
            logger.info(f"Alternating size pattern detected (ratio={ratio:.2f}, strength={calibrated_strength:.2f})")
            return {
                "found": True,
                "strength": min(0.92, calibrated_strength),
                "confidence": "high" if ratio >= 0.95 else "medium",
                "pattern": recent,
                "ratio": ratio,
                "next_expected": "Small" if recent[-1] == "Big" else "Big"
            }
        
        return {"found": False, "strength": 0.0, "details": "Ratio below threshold"}
    
    def _detect_repeating_pattern(self) -> Dict[str, Any]:
        """
        Detect repeating pattern like BB SS or SS BB with calibrated confidence.
        Requires consistent pair repetition for robust signal.
        """
        if len(self.sizes) < 4:
            return {"found": False, "strength": 0.0}
        
        # Widen from 6 → 10 draws for more confident pair matching
        recent = list(reversed(self.sizes[:10]))
        pairs = [recent[i:i+2] for i in range(0, len(recent) - 1, 2)]
        
        if len(pairs) >= 2:
            if all(pairs[i] == pairs[i+1] for i in range(len(pairs) - 1)):
                pattern = pairs[0]
                # Calibrated strength: more consistent pairs = higher confidence
                pair_count = len(pairs)
                calibrated_strength = 0.72 + min(pair_count * 0.04, 0.12)  # Range: 0.72-0.84
                logger.info(f"Repeating pattern detected: {pattern} ({pair_count} pairs, strength={calibrated_strength:.2f})")
                return {
                    "found": True,
                    "strength": min(0.84, calibrated_strength),
                    "confidence": "high" if pair_count >= 3 else "medium",
                    "pattern": pattern,
                    "pair_count": pair_count,
                    "next_expected": pattern
                }
        
        return {"found": False, "strength": 0.0}
    
    def _detect_current_streak(self) -> Dict[str, Any]:
        """Detect current streak (consecutive same values)."""
        if not self.sizes:
            return {"length": 0, "type": None, "direction": None}
        
        current = self.sizes[0]
        length = 1

        for i in range(1, len(self.sizes)):
            if self.sizes[i] == current:
                length += 1
            else:
                break
        
        return {
            "length": length,
            "type": current,
            "direction": "will_reverse" if length >= 3 else "may_continue"
        }
    
    def _detect_streak_history(self) -> List[Dict[str, Any]]:
        """Analyze historical streaks."""
        streaks: List[Dict[str, Any]] = []
        if not self.sizes:
            return streaks
        
        chrono_sizes = list(reversed(self.sizes))
        current_type = chrono_sizes[0]
        current_length = 1

        for i in range(1, len(chrono_sizes)):
            if chrono_sizes[i] == current_type:
                current_length += 1
            else:
                if current_length >= 2:
                    streaks.append({
                        "type": current_type,
                        "length": current_length
                    })
                current_type = chrono_sizes[i]
                current_length = 1
        
        return streaks
    
    # ==================== COLOR PATTERNS ====================
    
    def detect_color_pattern(self) -> Dict[str, Any]:
        """
        Detect color patterns: 1A1B, 2A2B, 3A3B, etc.
        
        Returns:
            Dictionary with detected color patterns
        """
        patterns: Dict[str, Any] = {
            "nAnB_pattern": self._detect_nAnB_pattern(),
            "color_cycle": self._detect_color_cycle(),
            "dominant_color": self._get_dominant_color(),
            "pattern_type": None,
            "pattern_strength": 0.0
        }
        
        if patterns["nAnB_pattern"]["type"]:
            patterns["pattern_type"] = patterns["nAnB_pattern"]["type"]
            patterns["pattern_strength"] = patterns["nAnB_pattern"]["strength"]
        elif patterns["color_cycle"]["detected"]:
            patterns["pattern_type"] = "Color Cycle"
            patterns["pattern_strength"] = patterns["color_cycle"]["strength"]
        
        return patterns
    
    def _detect_nAnB_pattern(self) -> Dict[str, Any]:
        """
        Detect nAnB patterns (1A1B, 2A2B, 3A3B, 4A4B).
        A = first color repeated n times, B = second color repeated n times
        Uses extended window and validates repetition across more samples for robust signal.
        """
        if len(self.colors) < 4:
            return {"type": None, "strength": 0.0}
        
        # Widen from 8 → 12 for higher-confidence nAnB detection
        recent = list(reversed(self.colors[:12]))

        # Check for patterns, prioritizing longer runs for more stable signal
        for n in [2, 3, 4, 1]:  # Check 2A2B before 1A1B to favor more stable patterns
            pattern_length = n * 2
            if len(recent) >= pattern_length:
                segment = recent[-pattern_length:]
                first_part = segment[:n]
                second_part = segment[n:]
                
                if all(c == first_part[0] for c in first_part) and \
                   all(c == second_part[0] for c in second_part) and \
                   first_part[0] != second_part[0]:
                    
                    pattern_name = f"{n}A{n}B"
                    # Calibrated strength: longer patterns are more reliable
                    # 2A2B: 0.72, 3A3B: 0.78, 4A4B: 0.84, 1A1B: 0.65
                    calibrated_strength = 0.62 + n * 0.06
                    logger.info(f"Color pattern {pattern_name} detected (strength: {calibrated_strength:.2f})")
                    return {
                        "type": pattern_name,
                        "strength": min(0.88, calibrated_strength),
                        "confidence": "high" if n >= 2 else "medium",
                        "pattern": segment,
                        "next_color": second_part[0] if len(recent) % (2 * n) == 0 else first_part[0]
                    }
        
        return {"type": None, "strength": 0.0}
    
    def _detect_color_cycle(self) -> Dict[str, Any]:
        """
        Detect repeating color cycles with robust confidence calibration.
        Favors longer, more stable cycles and validates with extended match ratio.
        """
        if len(self.colors) < 4:
            return {"detected": False, "strength": 0.0}
        
        # Widen from 6 → 9 to validate the cycle over more rounds
        recent = list(reversed(self.colors[:9]))

        # Check for 3-color and 2-color cycles (order: longer cycles first for stability)
        for cycle_length in [3, 2]:
            if len(recent) >= cycle_length * 2:
                cycle = recent[:cycle_length]
                matches = sum(1 for i in range(cycle_length, len(recent))
                             if recent[i] == cycle[(i - cycle_length) % cycle_length])
                ratio = matches / max(len(recent) - cycle_length, 1)
                
                # Calibrated thresholds: require higher ratio for 3-color (more restrictive)
                threshold = 0.80 if cycle_length == 3 else 0.72
                
                if ratio >= threshold:
                    # Calibrated strength: 3-cycles are more stable
                    calibrated_strength = 0.70 + ratio * 0.20 if cycle_length == 3 else 0.64 + ratio * 0.16
                    logger.info(f"Color cycle detected (length={cycle_length}, ratio={ratio:.2f}, strength={calibrated_strength:.2f})")
                    return {
                        "detected": True,
                        "cycle_length": cycle_length,
                        "cycle": cycle,
                        "strength": min(0.85, calibrated_strength),
                        "confidence": "high" if ratio >= 0.85 else "medium",
                        "match_ratio": ratio,
                        "next_color": cycle[len(recent) % cycle_length]
                    }
        
        return {"detected": False, "strength": 0.0}
    
    def _get_dominant_color(self) -> Dict[str, Any]:
        """
        Get most frequent color in recent draws with explicit strength signal.
        Strength is calibrated based on dominance percentage to indicate confidence.
        """
        color_count = Counter(self.colors)
        if not color_count:
            return {"color": None, "frequency": 0, "percentage": 0.0, "strength": 0.0}
        
        most_common = color_count.most_common(1)[0]
        percentage = (most_common[1] / len(self.colors)) * 100
        
        # Calibrated strength: 50%+ = 0.7-0.9 strength, <50% = weaker
        if percentage >= 60:
            strength = 0.85
            confidence = "high"
        elif percentage >= 55:
            strength = 0.75
            confidence = "medium" 
        elif percentage >= 50:
            strength = 0.65
            confidence = "medium"
        else:
            strength = 0.45
            confidence = "low"
        
        return {
            "color": most_common[0],
            "frequency": most_common[1],
            "percentage": percentage,
            "strength": strength,
            "confidence": confidence,
            "color_distribution": dict(color_count)
        }
    
    # ==================== CYCLE DETECTION ====================
    
    def detect_cycles(self) -> List[Dict[str, Any]]:
        """
        Detect repeating cycles (2-round, 3-round, 4-round, 6-round).
        
        Returns:
            List of detected cycles with strength
        """
        cycles: List[Dict[str, Any]] = []
        
        for cycle_length in [2, 3, 4, 6]:
            cycle_data = self._check_cycle(cycle_length)
            if cycle_data["strength"] > 0:
                cycles.append(cycle_data)
        
        return sorted(cycles, key=lambda x: x["strength"], reverse=True)
    
    def _check_cycle(self, cycle_length: int) -> Dict[str, Any]:
        """Check if pattern repeats in given cycle length."""
        if len(self.draws) < cycle_length * 2:
            return {"cycle_length": cycle_length, "strength": 0.0, "pattern": None}

        # Use 4x window for better cycle confirmation on long histories.
        recent = list(reversed(self.draws[:cycle_length * 4]))
        
        # Check if pattern repeats
        pattern = recent[:cycle_length]
        matches = 0
        
        for i in range(cycle_length, len(recent)):
            if recent[i] == pattern[i % cycle_length]:
                matches += 1
        
        strength = matches / (len(recent) - cycle_length)
        
        if strength > 0.6:  # More than 60% match
            logger.info(f"{cycle_length}-round cycle detected with strength {strength:.2f}")
            return {
                "cycle_length": cycle_length,
                "pattern": pattern,
                "strength": strength,
                "next_number": pattern[len(recent) % cycle_length]
            }
        
        return {"cycle_length": cycle_length, "strength": 0.0, "pattern": None}
    
    # ==================== UTILITY METHODS ====================
    
    def get_size_distribution(self) -> Dict[str, int]:
        """Get Big/Small distribution."""
        size_count = Counter(self.sizes)
        return dict(size_count)
    
    def get_number_frequency(self) -> Dict[int, int]:
        """Get frequency of each number 0-9."""
        freq = Counter(self.draws)
        return {i: freq.get(i, 0) for i in range(10)}
    
    def analyze_all_patterns(self) -> Dict[str, Any]:
        """Run all pattern detections and return summary."""
        # Try to use the trained LSTM model first; fall back to Markov chain.
        try:
            from sequence_model import get_global_model  # lazy — avoids import cycle
            deep_model = get_global_model()
            if deep_model.is_ready:
                seq_summary = deep_model.get_summary(self.draws[:20])
                seq_summary["source"] = "lstm"
            else:
                raise RuntimeError("LSTM not ready")
        except Exception:
            markov = LLMSequenceAI(self.draws)
            seq_summary = markov.get_model_summary(self.draws[:Config.SEQUENCE_MAX_CONTEXT])
            seq_summary["source"] = "markov"

        return {
            "size_patterns": self.detect_size_pattern(),
            "color_patterns": self.detect_color_pattern(),
            "cycles": self.detect_cycles(),
            "sequence_patterns": seq_summary,
            "number_frequency": self.get_number_frequency(),
            "size_distribution": self.get_size_distribution(),
            "recent_draws": self.draws,
            "recent_sizes": self.sizes,
            "recent_colors": self.colors
        }


__all__ = ["PatternDetector", "SizeMapper", "ColorMapper", "LLMSequenceAI"]
