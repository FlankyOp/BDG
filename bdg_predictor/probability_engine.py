"""
Probability Engine Module
Calculates weighted probabilities and confidence scores for predictions.
"""

import logging
from typing import Any, List, Dict, Tuple, Optional, cast
from pattern_detector import SizeMapper, ColorMapper, PatternDetector
from config import Config

logger = logging.getLogger(__name__)


class ProbabilityEngine:
    """Calculates probabilities and scores for number predictions."""
    
    def __init__(self, draws: List[int], patterns: Dict[str, Any], weight_profile: Optional[Dict[str, float]] = None):
        """
        Initialize probability engine.
        
        Args:
            draws: List of recent draw numbers
            patterns: Pattern analysis results from PatternDetector
        """
        self.draws = list(draws or [])
        self.patterns: Dict[str, Any] = patterns or {}
        self.detector = PatternDetector(self.draws)
        self.weights = self._resolve_weights(weight_profile)

    def _size_patterns(self) -> Dict[str, Any]:
        return self.patterns.get("size_patterns", {})

    def _color_patterns(self) -> Dict[str, Any]:
        return self.patterns.get("color_patterns", {})

    def _cycles(self) -> List[Dict[str, Any]]:
        raw_cycles = self.patterns.get("cycles", [])
        if not isinstance(raw_cycles, list):
            return []
        return cast(List[Dict[str, Any]], raw_cycles)

    def _sequence_patterns(self) -> Dict[str, Any]:
        raw_sequence = self.patterns.get("sequence_patterns", {})
        if not isinstance(raw_sequence, dict):
            return {}
        return cast(Dict[str, Any], raw_sequence)

    def _sequence_scores(self) -> Dict[int, float]:
        raw_scores = self._sequence_patterns().get("scores", {})
        if not isinstance(raw_scores, dict):
            return {}

        typed_scores = cast(Dict[Any, Any], raw_scores)
        normalized: Dict[int, float] = {}
        for key, value in typed_scores.items():
            try:
                number = int(key)
                score = float(value)
            except (TypeError, ValueError):
                continue

            if 0 <= number <= 9:
                normalized[number] = max(0.0, score)

        return normalized

    def _color_family(self, color: Optional[str]) -> Optional[str]:
        if not color:
            return None

        normalized = str(color)
        if normalized == "Violet":
            return "Red"
        if normalized in {"Red", "Green"}:
            return normalized
        return None

    def _matches_preferred_color(self, number_color: str, preferred_color: Optional[str]) -> bool:
        if not preferred_color:
            return False

        if number_color == preferred_color:
            return True

        number_family = self._color_family(number_color)
        preferred_family = self._color_family(preferred_color)
        return number_family is not None and number_family == preferred_family

    def _repeat_penalty_multiplier(self, number: int) -> float:
        """Return a multiplier that penalizes immediate/recent repeats."""
        if not self.draws:
            return 1.0

        recent_2 = self.draws[:2]
        recent_5 = self.draws[:5]
        recent_10 = self.draws[:10]
        multiplier = 1.0

        if number == self.draws[0]:
            multiplier *= 0.55

        if recent_2.count(number) == 2:
            multiplier *= 0.70

        if number == 0 and recent_10.count(0) >= 2:
            multiplier *= 0.85
        if number == 0 and recent_5.count(0) >= 2:
            multiplier *= 0.75

        if recent_5.count(number) >= 3:
            multiplier *= 0.80

        return multiplier

    def _extract_preferred_color(self) -> Tuple[Optional[str], float]:
        cp = self._color_patterns()
        
        nAnB = cp.get("nAnB_pattern", {})
        if nAnB.get("type") and nAnB.get("strength", 0) >= 0.65:
            next_color = str(nAnB.get("next_color"))
            strength = float(nAnB.get("strength", 0.65))
            confidence = min(0.92, 0.65 + strength * 0.30)
            logger.debug(f"Color hierarchy: nAnB pattern '{nAnB['type']}' -> {next_color} (conf={confidence:.2f})")
            return (next_color, confidence)
        
        color_cycle = cp.get("color_cycle", {})
        if color_cycle.get("detected"):
            next_color = str(color_cycle.get("next_color"))
            cycle_strength = float(color_cycle.get("strength", 0.70))
            confidence = min(0.88, 0.60 + cycle_strength * 0.25)
            logger.debug(f"Color hierarchy: cycle pattern -> {next_color} (conf={confidence:.2f})")
            return (next_color, confidence)
        
        dom = cp.get("dominant_color", {})
        if dom.get("color"):
            percentage = float(dom.get("percentage", 0.0))
            if percentage >= 55:
                dom_color = str(dom["color"])
                dom_strength = float(dom.get("strength", 0.45))
                confidence = min(0.78, 0.45 + dom_strength * 0.30)
                logger.debug(f"Color hierarchy: dominant '{dom_color}' {percentage:.1f}% (conf={confidence:.2f})")
                return (dom_color, confidence)
        
        logger.debug("Color hierarchy: no strong signal, will blend all colors")
        return (None, 0.0)

    def _extract_preferred_size(self) -> Tuple[Optional[str], float]:
        sp = self._size_patterns()
        
        alt = sp.get("alternating", {})
        if alt.get("found", False):
            alt_strength = float(alt.get("strength", 0.78))
            if alt_strength >= 0.75:
                next_size = str(alt.get("next_expected"))
                confidence = min(0.90, 0.70 + alt_strength * 0.25)
                logger.debug(f"Size hierarchy: alternating pattern -> {next_size} (conf={confidence:.2f})")
                return (next_size, confidence)
        
        rep = sp.get("repeating", {})
        if rep.get("found", False):
            rep_strength = float(rep.get("strength", 0.72))
            next_size = str(rep.get("next_expected"))
            confidence = min(0.85, 0.65 + rep_strength * 0.20)
            logger.debug(f"Size hierarchy: repeating pattern -> {next_size} (conf={confidence:.2f})")
            return (next_size, confidence)
        
        streak = sp.get("current_streak", {})
        streak_len = int(streak.get("length", 0))
        if streak_len >= Config.MIN_STREAK_LENGTH:
            streak_type = str(streak.get("type"))
            next_expected = "Small" if streak_type == "Big" else "Big"
            confidence = min(0.80, 0.50 + streak_len * 0.08)
            logger.debug(f"Size hierarchy: {streak_len}-streak reversal -> {next_expected} (conf={confidence:.2f})")
            return (next_expected, confidence)
        
        logger.debug("Size hierarchy: no strong signal, will blend all sizes")
        return (None, 0.0)

    def _resolve_weights(self, profile: Optional[Dict[str, float]]) -> Dict[str, float]:
        """Resolve active weights and normalize them to sum to 1."""
        defaults = {
            "trend": Config.WEIGHT_TREND,
            "frequency": Config.WEIGHT_FREQUENCY,
            "cycle": Config.WEIGHT_CYCLE,
            "streak": Config.WEIGHT_STREAK,
            "noise": Config.WEIGHT_NOISE,
            "sequence": Config.WEIGHT_SEQUENCE,
        }
        if not profile:
            return defaults

        merged = {
            "trend": float(profile.get("trend", defaults["trend"])),
            "frequency": float(profile.get("frequency", defaults["frequency"])),
            "cycle": float(profile.get("cycle", defaults["cycle"])),
            "streak": float(profile.get("streak", defaults["streak"])),
            "noise": float(profile.get("noise", defaults["noise"])),
            "sequence": float(profile.get("sequence", defaults["sequence"])),
        }
        total = sum(max(v, 0.0) for v in merged.values()) or 1.0
        return {k: max(v, 0.0) / total for k, v in merged.items()}

    def get_weight_components(self, number: int) -> Dict[str, float]:
        """Return per-factor components for learning feedback."""
        return {
            "trend": self.calculate_trend_weight(number),
            "frequency": self.calculate_frequency_weight(number),
            "cycle": self.calculate_cycle_weight(number),
            "streak": self.calculate_streak_weight(number),
            "noise": self.calculate_noise_weight(number),
            "sequence": self.calculate_sequence_weight(number),
        }
    
    def calculate_trend_weight(self, number: int) -> float:
        """Calculate trend weight based on recent patterns."""
        weight = 0.0
        
        size = SizeMapper.get_size(number)
        size_patterns = self._size_patterns()
        current_streak = size_patterns.get("current_streak", {})
        
        pattern_type = str(size_patterns.get("pattern_type", ""))
        if pattern_type == "Streak":
            streak_type = str(current_streak.get("type", ""))
            streak_length = int(current_streak.get("length", 0))
            if size != streak_type and streak_length >= Config.MIN_STREAK_LENGTH:
                weight += 0.35
        
        recent_sizes = self.detector.sizes[:5]
        if recent_sizes.count("Big") >= 3:
            if size == "Small":
                weight += Config.SIZE_BALANCE_BOOST
        elif recent_sizes.count("Small") >= 3:
            if size == "Big":
                weight += Config.SIZE_BALANCE_BOOST
        
        freq = self.detector.get_number_frequency()
        if freq.get(number, 0) == 0:
            weight += 0.10
        
        return min(weight, 1.0)

    def calculate_frequency_weight(self, number: int) -> float:
        """Calculate frequency weight based on historical frequency."""
        freq = self.detector.get_number_frequency()
        max_freq = max(freq.values()) if freq.values() else 1
        normalized_freq = freq.get(number, 0) / max_freq if max_freq > 0 else 0
        
        weight = 1.0 - normalized_freq
        
        return weight
    
    def calculate_cycle_weight(self, number: int) -> float:
        """Calculate weight based on cycle detection."""
        cycles = self._cycles()
        
        if not cycles:
            return 0.0
        
        best_cycle = max(cycles, key=lambda cycle: float(cycle.get("strength", 0.0)))
        strength = float(best_cycle.get("strength", 0.0))
        if strength < 0.5:
            return 0.0
        
        next_number = best_cycle.get("next_number")
        if next_number == number:
            return strength * 0.9
        
        pattern = best_cycle.get("pattern", [])
        if isinstance(pattern, list) and number in pattern:
            return strength * 0.6
        
        return 0.0

    def calculate_streak_weight(self, number: int) -> float:
        """Calculate weight based on streak analysis."""
        streak = self._size_patterns().get("current_streak", {})
        streak_length = int(streak.get("length", 0))
        
        if streak_length < 2:
            return 0.0
        
        size = SizeMapper.get_size(number)
        
        if streak_length >= Config.MIN_STREAK_LENGTH and size != str(streak.get("type", "")):
            return min(0.6 + (streak_length * 0.05), 1.0)

        return 0.0

    def calculate_noise_weight(self, number: int) -> float:
        """Calculate noise weight (randomness dampening)."""
        if number not in self.draws:
            return 0.0

        if number not in self.draws[:3]:
            return 0.15

        last_appearance = self.draws.index(number)
        recency_factor = last_appearance / max(len(self.draws), 1)
        
        return recency_factor * 0.10

    def calculate_sequence_weight(self, number: int) -> float:
        """Calculate next-token-style weight from the 500-draw sequence learner."""
        sequence_scores = self._sequence_scores()
        if not sequence_scores:
            return 0.0

        probability = float(sequence_scores.get(number, 0.0))
        if probability <= 0.0:
            return 0.0

        top_probability = max(sequence_scores.values()) if sequence_scores else probability
        if top_probability <= 0.0:
            return 0.0

        relative_strength = probability / top_probability
        return min(1.0, probability * 3.0 + relative_strength * 0.35)

    def calculate_color_weight(self, number: int) -> float:
        """Calculate color-based weight."""
        color = ColorMapper.get_color(number)
        color_patterns = self._color_patterns()
        dominant = color_patterns.get("dominant_color", {})
        
        color_pattern = str(color_patterns.get("pattern_type", ""))
        if color_pattern and "A" in color_pattern:
            nAnB = color_patterns.get("nAnB_pattern", {})
            if color == str(nAnB.get("next_color", "")):
                return Config.COLOR_BOOST
        
        if dominant.get("color") and color != str(dominant["color"]):
            percentage = float(dominant.get("percentage", 0.0))
            boost = 1.0 - (percentage / 100)
            return boost * 0.15
        
        return 0.0

    def calculate_confidence_score(self, number: int) -> float:
        """Calculate overall confidence score using weighted formula."""
        comps = self.get_weight_components(number)
        trend = comps["trend"]
        frequency = comps["frequency"]
        cycle = comps["cycle"]
        streak = comps["streak"]
        noise = comps["noise"]
        sequence = comps["sequence"]
        color = self.calculate_color_weight(number)
        
        score = (
            trend * self.weights["trend"] +
            frequency * self.weights["frequency"] +
            cycle * self.weights["cycle"] +
            streak * self.weights["streak"] +
            noise * self.weights["noise"] +
            sequence * self.weights["sequence"]
        )
        
        if color > 0.1:
            score = score * (1.0 - Config.COLOR_BLEND_WEIGHT) + color * Config.COLOR_BLEND_WEIGHT

        score *= self._repeat_penalty_multiplier(number)
        
        return min(score, 1.0)
    
    def rank_all_numbers(self) -> List[Tuple[int, float, str, str]]:
        """Rank all numbers 0-9 using strict hierarchy: color -> size -> number score."""
        preferred_color, color_conf = self._extract_preferred_color()
        preferred_size, size_conf = self._extract_preferred_size()
        logger.info(
            "Hierarchy targets: color=%s (%.2f), size=%s (%.2f)",
            preferred_color or "None",
            color_conf,
            preferred_size or "None",
            size_conf,
        )
        
        all_rankings: List[Dict[str, Any]] = []
        for number in range(10):
            score = self.calculate_confidence_score(number)
            size = SizeMapper.get_size(number)
            color = ColorMapper.get_color(number)
            
            tier = 3
            
            if preferred_color and color_conf >= 0.60:
                if self._matches_preferred_color(color, preferred_color):
                    tier = 1
                elif preferred_size and size_conf >= 0.60 and size == preferred_size:
                    tier = 2
                else:
                    tier = 3
            elif preferred_size and size_conf >= 0.60:
                if size == preferred_size:
                    tier = 1
                else:
                    tier = 2
            
            all_rankings.append({
                "number": number,
                "score": score,
                "size": size,
                "color": color,
                "tier": tier,
                "hierarchy_metadata": {
                    "preferred_color": preferred_color,
                    "color_conf": color_conf,
                    "preferred_size": preferred_size,
                    "size_conf": size_conf,
                    "assigned_tier": tier
                }
            })
        
        all_rankings.sort(key=lambda x: (x["tier"], -x["score"]))
        
        rankings: List[Tuple[int, float, str, str]] = [
            (r["number"], r["score"], r["size"], r["color"]) for r in all_rankings
        ]
        
        logger.info(f"Hierarchical rankings (color_signal={color_conf:.2f}, size_signal={size_conf:.2f}):")
        for i, (num, score, size, color) in enumerate(rankings[:5]):
            tier = all_rankings[i]["tier"]
            logger.info(f"  {i+1}. {num}: {score:.2%} ({size}, {color}) [tier={tier}]")
        
        return rankings
    
    def get_top_predictions(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """Get top N predictions with detailed information."""
        rankings = self.rank_all_numbers()
        predictions: List[Dict[str, Any]] = []
        
        for i, (number, score, size, color) in enumerate(rankings[:top_n]):
            predictions.append({
                "rank": i + 1,
                "number": number,
                "confidence": score,
                "size": size,
                "color": color,
                "accuracy_percentage": score * 100
            })
        
        return predictions

    def explain_prediction(self, number: int) -> Dict[str, float]:
        """Generate numeric explanation components for a prediction."""
        return {
            "trend_weight": self.calculate_trend_weight(number),
            "frequency_weight": self.calculate_frequency_weight(number),
            "cycle_weight": self.calculate_cycle_weight(number),
            "streak_weight": self.calculate_streak_weight(number),
            "noise_weight": self.calculate_noise_weight(number),
            "sequence_weight": self.calculate_sequence_weight(number),
            "total_score": self.calculate_confidence_score(number),
        }
    
    def get_probability_analysis(self) -> Dict[str, Any]:
        """Get comprehensive probability analysis."""
        rankings = self.rank_all_numbers()
        top_3 = rankings[:3]
        
        return {
            "top_predictions": self.get_top_predictions(3),
            "all_rankings": [
                {
                    "number": num,
                    "score": score,
                    "size": size,
                    "color": color
                }
                for num, score, size, color in rankings
            ],
            "primary": {
                "number": top_3[0][0],
                "score": top_3[0][1],
                "size": top_3[0][2],
                "color": top_3[0][3]
            },
            "alternative": {
                "number": top_3[1][0],
                "score": top_3[1][1],
                "size": top_3[1][2],
                "color": top_3[1][3]
            } if len(top_3) > 1 else None,
            "backup": {
                "number": top_3[2][0],
                "score": top_3[2][1],
                "size": top_3[2][2],
                "color": top_3[2][3]
            } if len(top_3) > 2 else None
        }
    
    # ==================== 500-DRAW ANALYSIS (Alternative Predictions) ====================
    
    def get_frequency_only_prediction(self) -> Dict[str, Any]:
        """
        Pure frequency-based prediction from 500 draws.
        
        Counts occurrences in the draw history, ignores patterns.
        Useful as a baseline / sanity check.
        """
        freq: Dict[int, int] = {}
        for num in self.draws:
            freq[num] = freq.get(num, 0) + 1
        
        ranked = sorted(freq.items(), key=lambda x: -x[1])
        if not ranked:
            return {"number": 0, "score": 0.0, "size": "Small", "color": "Red", "reasoning": "No draw data"}
        
        top_num, top_count = ranked[0]
        score = (top_count / len(self.draws)) if self.draws else 0.0
        
        return {
            "number": top_num,
            "score": score,
            "size": SizeMapper.get_size(top_num),
            "color": ColorMapper.get_color(top_num),
            "reasoning": f"Highest frequency ({top_count}/{len(self.draws)} = {score:.1%})",
            "method": "frequency_500"
        }
    
    def get_pattern_filtered_prediction(self) -> Dict[str, Any]:
        """
        Frequency prediction filtered by detected patterns.
        
        Boosts numbers that match the color/size trend detected in the pattern analyzer.
        """
        preferred_color, color_conf = self._extract_preferred_color()
        preferred_size, size_conf = self._extract_preferred_size()
        
        freq: Dict[int, float] = {}
        for num in self.draws:
            matches_color = preferred_color and self._matches_preferred_color(
                ColorMapper.get_color(num), preferred_color
            ) and color_conf >= 0.50
            matches_size = preferred_size and SizeMapper.get_size(num) == preferred_size and size_conf >= 0.50
            
            base = 1.0
            if matches_color:
                base += 2.0  # +200% boost for color match
            if matches_size:
                base += 1.5  # +150% boost for size match
            
            freq[num] = freq.get(num, 0) + base
        
        ranked = sorted(freq.items(), key=lambda x: -x[1])
        if not ranked:
            return {"number": 0, "score": 0.0, "size": "Small", "color": "Red", "reasoning": "No matches"}
        
        top_num, top_score = ranked[0]
        max_score = sum(1.0 for _ in self.draws) + (2.0 + 1.5) * len(self.draws)  # max possible
        normalized_score = (top_score / max_score) if max_score > 0 else 0.0
        
        reasoning_parts = [f"Top pattern-match: #{top_num}"]
        if preferred_color and color_conf >= 0.50:
            reasoning_parts.append(f"Color {preferred_color} ({color_conf:.0%})")
        if preferred_size and size_conf >= 0.50:
            reasoning_parts.append(f"Size {preferred_size} ({size_conf:.0%})")
        
        return {
            "number": top_num,
            "score": normalized_score,
            "size": SizeMapper.get_size(top_num),
            "color": ColorMapper.get_color(top_num),
            "reasoning": " + ".join(reasoning_parts),
            "method": "pattern_filtered_500"
        }


__all__ = ["ProbabilityEngine"]
