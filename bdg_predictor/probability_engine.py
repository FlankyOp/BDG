"""
Probability Engine Module
Calculates weighted probabilities and confidence scores for predictions.
"""

import logging
from typing import Any, List, Dict, Tuple, Optional
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
        self.draws = draws
        self.patterns: Dict[str, Any] = patterns
        self.detector = PatternDetector(draws)
        self.weights = self._resolve_weights(weight_profile)

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
        
        if self.patterns["size_patterns"]["pattern_type"] == "Streak":
            # Streak reversal: predict opposite
            streak_type = self.patterns["size_patterns"]["current_streak"]["type"]
            if size != streak_type and self.patterns["size_patterns"]["current_streak"]["length"] >= 3:
                weight += 0.35
        
        # Apply size balance rule
        recent_sizes = self.detector.sizes[-5:]
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
        if number not in self.draws[-3:]:
            return 0.15
        
        # Recent appearance -> decrease weight
        last_appearance = len(self.draws) - 1 - self.draws[::-1].index(number)
        recency_factor = last_appearance / len(self.draws)
        
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
        
        return min(score, 1.0)
    
    def rank_all_numbers(self) -> List[Tuple[int, float, str, str]]:
        """
        Rank all numbers 0-9 by confidence score.
        
        Returns:
            List of (number, score, size, color) sorted by score descending
        """
        rankings: List[Tuple[int, float, str, str]] = []
        
        for number in range(10):
            score = self.calculate_confidence_score(number)
            size = SizeMapper.get_size(number)
            color = ColorMapper.get_color(number)
            
            rankings.append((number, score, size, color))
        
        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)
        
        logger.info("Number rankings:")
        for num, score, size, color in rankings[:5]:
            logger.info(f"  {num}: {score:.2%} ({size}, {color})")
        
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
