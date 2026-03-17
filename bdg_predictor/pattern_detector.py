"""
Pattern Detector Module
Analyzes game patterns for size, color, streaks, and cycles.
"""

import logging
from typing import Any, List, Dict
from collections import Counter

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


class PatternDetector:
    """Detects patterns in game results."""
    
    def __init__(self, draws: List[int]):
        """
        Initialize pattern detector.
        
        Args:
            draws: List of recent draw numbers (up to 500)
        """
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
        """Detect alternating B/S or S/B pattern."""
        if len(self.sizes) < 4:
            return {"found": False, "strength": 0.0, "details": "Insufficient data"}
        
        # Widen to last 15 draws; require ≥90% alternating transitions
        recent = self.sizes[-15:]
        alt_count = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        ratio = alt_count / max(len(recent) - 1, 1)

        if ratio >= 0.90:
            strength = min(0.90, 0.70 + ratio * 0.20)
            logger.info("Alternating size pattern detected")
            return {
                "found": True,
                "strength": strength,
                "pattern": recent,
                "next_expected": "Small" if recent[-1] == "Big" else "Big"
            }
        
        return {"found": False, "strength": 0.0}
    
    def _detect_repeating_pattern(self) -> Dict[str, Any]:
        """Detect repeating pattern like BB SS or SS BB."""
        if len(self.sizes) < 4:
            return {"found": False, "strength": 0.0}
        
        # Widen from 6 → 10 draws for more confident pair matching
        recent = self.sizes[-10:]
        pairs = [recent[i:i+2] for i in range(0, len(recent) - 1, 2)]
        
        if len(pairs) >= 2:
            if all(pairs[i] == pairs[i+1] for i in range(len(pairs) - 1)):
                pattern = pairs[0]
                logger.info(f"Repeating pattern detected: {pattern}")
                return {
                    "found": True,
                    "strength": 0.75,
                    "pattern": pattern,
                    "next_expected": pattern
                }
        
        return {"found": False, "strength": 0.0}
    
    def _detect_current_streak(self) -> Dict[str, Any]:
        """Detect current streak (consecutive same values)."""
        if not self.sizes:
            return {"length": 0, "type": None, "direction": None}
        
        current = self.sizes[-1]
        length = 1
        
        for i in range(len(self.sizes) - 2, -1, -1):
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
        
        current_type = self.sizes[0]
        current_length = 1
        
        for i in range(1, len(self.sizes)):
            if self.sizes[i] == current_type:
                current_length += 1
            else:
                if current_length >= 2:
                    streaks.append({
                        "type": current_type,
                        "length": current_length
                    })
                current_type = self.sizes[i]
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
        """
        if len(self.colors) < 4:
            return {"type": None, "strength": 0.0}
        
        # Widen from 8 → 12 for higher-confidence nAnB detection
        recent = self.colors[-12:]

        # Check for patterns
        for n in [1, 2, 3, 4]:
            pattern_length = n * 2
            if len(recent) >= pattern_length:
                segment = recent[-pattern_length:]
                first_part = segment[:n]
                second_part = segment[n:]
                
                if all(c == first_part[0] for c in first_part) and \
                   all(c == second_part[0] for c in second_part) and \
                   first_part[0] != second_part[0]:
                    
                    pattern_name = f"{n}A{n}B"
                    logger.info(f"Color pattern {pattern_name} detected")
                    return {
                        "type": pattern_name,
                        "strength": min(0.9, 0.5 + n * 0.1),
                        "pattern": segment,
                        "next_color": second_part[0] if len(recent) % (2 * n) == 0 else first_part[0]
                    }
        
        return {"type": None, "strength": 0.0}
    
    def _detect_color_cycle(self) -> Dict[str, Any]:
        """Detect repeating color cycles."""
        if len(self.colors) < 4:
            return {"detected": False, "strength": 0.0}
        
        # Widen from 6 → 9 to validate the cycle over more rounds
        recent = self.colors[-9:]

        # Check for 2-color and 3-color cycles
        for cycle_length in [2, 3]:
            if len(recent) >= cycle_length * 2:
                cycle = recent[:cycle_length]
                matches = sum(1 for i in range(cycle_length, len(recent))
                             if recent[i] == cycle[(i - cycle_length) % cycle_length])
                ratio = matches / max(len(recent) - cycle_length, 1)
                if ratio >= 0.75:
                    strength = min(0.80, 0.60 + ratio * 0.25)
                    logger.info(f"Color cycle detected: {cycle}")
                    return {
                        "detected": True,
                        "cycle": cycle,
                        "strength": strength,
                        "next_color": cycle[len(recent) % cycle_length]
                    }
        
        return {"detected": False, "strength": 0.0}
    
    def _get_dominant_color(self) -> Dict[str, Any]:
        """Get most frequent color in recent draws."""
        color_count = Counter(self.colors)
        if not color_count:
            return {"color": None, "frequency": 0, "percentage": 0.0}
        
        most_common = color_count.most_common(1)[0]
        return {
            "color": most_common[0],
            "frequency": most_common[1],
            "percentage": (most_common[1] / len(self.colors)) * 100,
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
        recent = self.draws[-cycle_length * 4:]
        
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
        return {
            "size_patterns": self.detect_size_pattern(),
            "color_patterns": self.detect_color_pattern(),
            "cycles": self.detect_cycles(),
            "number_frequency": self.get_number_frequency(),
            "size_distribution": self.get_size_distribution(),
            "recent_draws": self.draws,
            "recent_sizes": self.sizes,
            "recent_colors": self.colors
        }


__all__ = ["PatternDetector", "SizeMapper", "ColorMapper"]
