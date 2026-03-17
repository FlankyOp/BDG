"""
Probability Engine Module
Calculates weighted probabilities and confidence scores for predictions.
"""

import logging
from typing import Any, List, Dict, Tuple, Optional, TypedDict
from typing_extensions import NotRequired
from pattern_detector import SizeMapper, ColorMapper, PatternDetector
from config import Config

logger = logging.getLogger(__name__)


class ProbabilityEngine:
    """Calculates probabilities and scores for number predictions."""
    
    class SizePatterns(TypedDict):
        pattern_type: str
        pattern_strength: float
        alternating: Dict[str, Any]
        repeating: Dict[str, Any]
        current_streak: Dict[str, Any]

    class ColorPatterns(TypedDict):
        pattern_type: str
        pattern_strength: float
        nAnB_pattern: Dict[str, Any]
        color_cycle: Dict[str, Any]
        dominant_color: Dict[str, Any]

    PatternsDict = TypedDict("PatternsDict", {
        "size_patterns": SizePatterns,
        "color_patterns": ColorPatterns,
        "cycles": list[Dict[str, Any]]
    })

    def __init__(self, draws: List[int], patterns: Dict[str, Any], weight_profile: Optional[Dict[str, float]] = None):
        """
        Initialize probability engine.
        
        Args:
            draws: List of recent draw numbers
            patterns: Pattern analysis results from PatternDetector
        """
        # Draws are provided newest-first by the fetcher/main engine.
        self.draws = draws
        self.patterns: PatternsDict = patterns
        self.detector = PatternDetector(draws)
        self.weights = self._resolve_weights(weight_profile)

    def _repeat_penalty_multiplier(self, number: int) -> float:
        """Return a multiplier that penalizes immediate/recent repeats."""
        if not self.draws:
            return 1.0

        recent_2 = self.draws[:2]
        recent_5 = self.draws[:5]
        recent_10 = self.draws[:10]
        multiplier = 1.0

        # Strongly discourage predicting the same immediate latest number.
        if number == self.draws[0]:
            multiplier *= 0.55

        # Additional dampening if a number is repeating in the last 2 rounds.
        if recent_2.count(number) == 2:
            multiplier *= 0.70

        # Extra anti-lock damping for zero if it is already overrepresented recently.
        if number == 0 and recent_10.count(0) >= 2:
            multiplier *= 0.85
        if number == 0 and recent_5.count(0) >= 2:
            multiplier *= 0.75

        # Penalize hot numbers that dominated the very recent short window.
        if recent_5.count(number) >= 3:
            multiplier *= 0.80

        return multiplier

    def _extract_preferred_color(self) -> Tuple[Optional[str], float]:
        """
        Extract the preferred color from detected patterns using hierarchy:
        1. nAnB pattern (if high confidence)
        2. Color cycle (if detected and strong)
        3. Dominant color (if frequency-based signal is strong enough)
        
        Returns:
            Tuple of (preferred_color: str or None, confidence: float between 0 and 1)
        """
        cp = self.patterns.get("color_patterns", {})
        
        # Check nAnB pattern first (most explicit pattern)
        nAnB = cp.get("nAnB_pattern", {})
        if nAnB.get("type") and nAnB.get("strength", 0) >= 0.65:
            next_color = nAnB.get("next_color")
            strength = float(nAnB.get("strength", 0.65))
            confidence = min(0.92, 0.65 + strength * 0.30)
            logger.debug(f"Color hierarchy: nAnB pattern '{nAnB['type']}' -> {next_color} (conf={confidence:.2f})")
            return (next_color, confidence)
        
        # Check color cycle
        color_cycle = cp.get("color_cycle", {})
        if color_cycle.get("detected"):
            next_color = color_cycle.get("next_color")
            cycle_strength = float(color_cycle.get("strength", 0.70))
            confidence = min(0.88, 0.60 + cycle_strength * 0.25)
            logger.debug(f"Color hierarchy: cycle pattern -> {next_color} (conf={confidence:.2f})")
            return (next_color, confidence)
        
        # Use dominant color if strong enough (>55% frequency)
        dom = cp.get("dominant_color", {})
        if dom.get("color"):
            percentage = float(dom.get("percentage", 0.0))
            if percentage >= 55:
                dom_strength = float(dom.get("strength", 0.45))
                confidence = min(0.78, 0.45 + dom_strength * 0.30)
                logger.debug(f"Color hierarchy: dominant '{dom['color']}' {percentage:.1f}% (conf={confidence:.2f})")
                return (dom["color"], confidence)
        
        # No strong color signal
        logger.debug("Color hierarchy: no strong signal, will blend all colors")
        return (None, 0.0)

    def _extract_preferred_size(self) -> Tuple[Optional[str], float]:
        """
        Extract the preferred size from detected patterns using hierarchy:
        1. Alternating pattern (if high confidence)
        2. Repeating pattern (if detected)
        3. Current streak direction (if strong enough)
        
        Returns:
            Tuple of (preferred_size: str or None, confidence: float between 0 and 1)
        """
        sp = self.patterns.get("size_patterns", {})
        
        # Check alternating pattern first
        alt = sp.get("alternating", {})
        if alt.get("found", False):
            alt_strength = float(alt.get("strength", 0.78))
            if alt_strength >= 0.75:
                next_size = alt.get("next_expected")
                confidence = min(0.90, 0.70 + alt_strength * 0.25)
                logger.debug(f"Size hierarchy: alternating pattern -> {next_size} (conf={confidence:.2f})")
                return (next_size, confidence)
        
        # Check repeating pattern
        rep = sp.get("repeating", {})
        if rep.get("found", False):
            rep_strength = float(rep.get("strength", 0.72))
            next_size = rep.get("next_expected")
            confidence = min(0.85, 0.65 + rep_strength * 0.20)
            logger.debug(f"Size hierarchy: repeating pattern -> {next_size} (conf={confidence:.2f})")
            return (next_size, confidence)
        
        # Check current streak (only if significant length)
        streak = sp.get("current_streak", {})
        streak_len = int(streak.get("length", 0))
        if streak_len >= 3:
            # Strong reversal signal
            streak_type = streak.get("type")
            next_expected = "Small" if streak_type == "Big" else "Big"
            confidence = min(0.80, 0.50 + streak_len * 0.08)
            logger.debug(f"Size hierarchy: {streak_len}-streak reversal -> {next_expected} (conf={confidence:.2f})")
            return (next_expected, confidence)
        
        # No strong size signal
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
        }
        if not profile:
            return defaults

        merged = {
            "trend": float(profile.get("trend", defaults["trend"])),
            "frequency": float(profile.get("frequency", defaults["frequency"])),
            "cycle": float(profile.get("cycle", defaults["cycle"])),
            "streak": float(profile.get("streak", defaults["streak"])),
            "noise": float(profile.get("noise", defaults["noise"])),
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
        }
    
    # ==================== WEIGHT CALCULATIONS ====================
    
    def calculate_trend_weight(self, number: int) -> float:
        """
        Calculate trend weight based on recent patterns.
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        weight = 0.0
        
        # Size trend
        size = SizeMapper.get_size(number)
        
        pattern_type = str(self.patterns["size_patterns"].get("pattern_type", ""))
        if pattern_type == "Streak":
            # Streak reversal: predict opposite
            streak_type = str(self.patterns["size_patterns"]["current_streak"].get("type", ""))
            streak_length = self.patterns["size_patterns"]["current_streak"].get("length", 0)
            if size != streak_type and streak_length >= 3:
                weight += 0.35
        
        # Apply size balance rule
        recent_sizes = self.detector.sizes[:5]
        if recent_sizes.count("Big") >= 3:
            # Majority Big -> boost Small
            if size == "Small":
                weight += 0.15
        elif recent_sizes.count("Small") >= 3:
            # Majority Small -> boost Big
            if size == "Big":
                weight += 0.15
        
        # Frequency analysis
        freq = self.detector.get_number_frequency()
        if freq[number] == 0:
            weight += 0.10  # Underrepresented numbers get boost
        
        return min(weight, 1.0)
    
    def calculate_frequency_weight(self, number: int) -> float:
        """
        Calculate frequency weight based on historical frequency.
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        freq = self.detector.get_number_frequency()
        # Normalize frequency to 0-1
        max_freq = max(freq.values()) if freq.values() else 1
        normalized_freq = freq[number] / max_freq if max_freq > 0 else 0
        
        # Inverse weight favors underrepresented numbers (reversion to mean)
        weight = 1.0 - normalized_freq
        
        return weight
    
    def calculate_cycle_weight(self, number: int) -> float:
        """
        Calculate weight based on cycle detection.
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        cycles = self.patterns["cycles"]
        
        if not cycles:
            return 0.0
        
        best_cycle = cycles[0]
        if best_cycle["strength"] < 0.5:
            return 0.0
        
        # Check if number would appear next in the cycle
        if "next_number" in best_cycle:
            if best_cycle["next_number"] == number:
                return best_cycle["strength"] * 0.9  # Max 0.81
        
        # Check if number exists in cycle
        if "pattern" in best_cycle and number in best_cycle["pattern"]:
            return best_cycle["strength"] * 0.6
        
        return 0.0
    
    def calculate_streak_weight(self, number: int) -> float:
        """
        Calculate weight based on streak analysis.
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        streak = self.patterns["size_patterns"]["current_streak"]
        
        if streak["length"] < 2:
            return 0.0
        
        size = SizeMapper.get_size(number)
        
        # If there's a strong streak, boost the opposite (clamped to 1.0)
        if streak["length"] >= 3:
            if size != streak["type"]:
                return min(0.6 + (streak["length"] * 0.05), 1.0)

        return 0.0
    
    def calculate_noise_weight(self, number: int) -> float:
        """
        Calculate noise weight (randomness dampening).
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        # If number hasn't appeared recently, add slight randomness boost
        if number not in self.draws[:3]:
            return 0.15

        # Newest-first indexing: lower index means more recent.
        last_appearance = self.draws.index(number)
        recency_factor = last_appearance / max(len(self.draws), 1)
        
        return recency_factor * 0.10
    
    def calculate_color_weight(self, number: int) -> float:
        """
        Calculate color-based weight.
        
        Args:
            number: Number to evaluate
            
        Returns:
            Weight between 0.0 and 1.0
        """
        color = ColorMapper.get_color(number)
        dominant = self.patterns["color_patterns"]["dominant_color"]
        
        # Color boost rule: if color trading detected, boost opposite
        color_pattern = self.patterns["color_patterns"]["pattern_type"]
        
        if color_pattern and "A" in color_pattern:  # nAnB pattern
            # Boost opposite color by 18%
            nAnB = self.patterns["color_patterns"]["nAnB_pattern"]
            if "next_color" in nAnB and color == nAnB["next_color"]:
                return 0.18
        
        # If color is underrepresented, boost it
        if dominant["color"] and color != dominant["color"]:
            boost = 1.0 - (dominant["percentage"] / 100)
            return boost * 0.15
        
        return 0.0
    
    # ==================== CONFIDENCE SCORING ====================
    
    def calculate_confidence_score(self, number: int) -> float:
        """
        Calculate overall confidence score using weighted formula.
        
        Confidence Score = 
            (TrendWeight * 0.30) +
            (FrequencyWeight * 0.25) +
            (CycleWeight * 0.20) +
            (StreakWeight * 0.15) +
            (NoiseWeight * 0.10)
        
        Args:
            number: Number to evaluate
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        comps = self.get_weight_components(number)
        trend = comps["trend"]
        frequency = comps["frequency"]
        cycle = comps["cycle"]
        streak = comps["streak"]
        noise = comps["noise"]
        color = self.calculate_color_weight(number)
        
        # Weighted formula — weights are sourced from Config (single source of truth)
        score = (
            trend * self.weights["trend"] +
            frequency * self.weights["frequency"] +
            cycle * self.weights["cycle"] +
            streak * self.weights["streak"] +
            noise * self.weights["noise"]
        )
        
        # Add color weight if significant
        if color > 0.1:
            score = score * 0.95 + color * 0.05

        # Prevent number lock behavior caused by immediate repeats/hot clustering.
        score *= self._repeat_penalty_multiplier(number)
        
        return min(score, 1.0)
    
    def rank_all_numbers(self) -> List[Tuple[int, float, str, str]]:
        """
        Rank all numbers 0-9 using strict hierarchy: color -> size -> number score.
        Numbers are grouped into tiers with color as primary gate, then size, then score.
        
        Returns:
            List of (number, score, size, color) sorted by hierarchy then score descending
        """
        # Extract hierarchy preferences
        preferred_color, color_conf = self._extract_preferred_color()
        preferred_size, size_conf = self._extract_preferred_size()
        
        # Build full rankings with metadata
        all_rankings: List[Dict[str, Any]] = []
        for number in range(10):
            score = self.calculate_confidence_score(number)
            size = SizeMapper.get_size(number)
            color = ColorMapper.get_color(number)
            
            # Determine hierarchy tier for this number
            # Tier 1: matches preferred color (if strong signal)
            # Tier 2: matches preferred size (if strong signal and no preferred color)
            # Tier 3: fallback (all numbers sorted by score)
            tier = 3  # Default fallback tier
            
            if preferred_color and color_conf >= 0.60:
                # Strong color signal means color-filtered tier
                # Check if this number's base color matches preferred (ignore Violet for base matching)
                base_color = "Red" if number in [0, 2, 4, 6, 8] else "Green"
                pref_base_color = "Red" if preferred_color in [0, 2, 4, 6, 8] else "Green"
                
                if base_color == pref_base_color or number == 5 and preferred_color == "Green/Violet":
                    tier = 1  # Primary color tier
                elif preferred_size and size_conf >= 0.60 and size == preferred_size:
                    tier = 2  # Secondary size tier (fallback within same color proximity)
                else:
                    tier = 3  # Fallback tier
            elif preferred_size and size_conf >= 0.60:
                # Size-only gating (no strong color signal)
                if size == preferred_size:
                    tier = 1  # Size tier becomes primary
                else:
                    tier = 2  # Secondary tier
            
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
        
        # Sort by: tier (ascending, so tier 1 first), then score (descending)
        all_rankings.sort(key=lambda x: (x["tier"], -x["score"]))
        
        # Convert back to tuple format for backward compatibility
        rankings: List[Tuple[int, float, str, str]] = [
            (r["number"], r["score"], r["size"], r["color"]) for r in all_rankings
        ]
        
        logger.info(f"Hierarchical rankings (color_signal={color_conf:.2f}, size_signal={size_conf:.2f}):")
        for i, (num, score, size, color) in enumerate(rankings[:5]):
            tier = all_rankings[i]["tier"]
            logger.info(f"  {i+1}. {num}: {score:.2%} ({size}, {color}) [tier={tier}]")
        
        return rankings
    
    # ==================== PREDICTION GENERATION ====================
    
    def get_top_predictions(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Get top N predictions with detailed information.
        
        Args:
            top_n: Number of predictions to return
            
        Returns:
            List of prediction dictionaries
        """
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
    
    def explain_prediction(self, number: int) -> Dict[str, str]:
        """
        Generate explanation for why a number was predicted.
        
        Args:
            number: Number to explain
            
        Returns:
            Dictionary with explanation details
        """
        explanation = {
            "trend_weight": f"{self.calculate_trend_weight(number):.2%}",
            "frequency_weight": f"{self.calculate_frequency_weight(number):.2%}",
            "cycle_weight": f"{self.calculate_cycle_weight(number):.2%}",
            "streak_weight": f"{self.calculate_streak_weight(number):.2%}",
            "noise_weight": f"{self.calculate_noise_weight(number):.2%}",
            "total_score": f"{self.calculate_confidence_score(number):.2%}"
        }
        
        return explanation
    
    def get_probability_analysis(self) -> Dict[str, Any]:
        """
        Get comprehensive probability analysis.
        
        Returns:
            Dictionary with analysis details
        """
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


__all__ = ["ProbabilityEngine"]
