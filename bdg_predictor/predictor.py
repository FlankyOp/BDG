"""
Predictor Module
Main prediction orchestrator combining all analysis components.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from pattern_detector import PatternDetector
from probability_engine import ProbabilityEngine
from config import Config

logger = logging.getLogger(__name__)


class Predictor:
    """Main predictor orchestrator."""

    PRIMARY_LABEL = "Primary"
    ALTERNATIVE_LABEL = "Alternative"
    BACKUP_LABEL = "Backup"
    SECTION_WIDTH = 40
    
    def __init__(self, draws: List[int], period: Optional[str] = None, weight_profile: Optional[Dict[str, float]] = None):
        """
        Initialize predictor.
        
        Args:
            draws: List of recent draw numbers
            period: Current period ID
            weight_profile: Optional adaptive weight profile
        """
        if not draws:
            raise ValueError("Predictor requires at least one draw")
        if any(draw < 0 or draw > 9 for draw in draws):
            raise ValueError("Predictor draws must be integers in the range 0-9")

        self.draws = draws
        self.period = period
        self.timestamp = datetime.now()
        self.weight_profile = weight_profile
        
        # Initialize components
        self.pattern_detector = PatternDetector(draws)
        self.patterns = self.pattern_detector.analyze_all_patterns()
        self.probability_engine = ProbabilityEngine(draws, self.patterns, weight_profile=weight_profile)

    def _prediction_entry(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        accuracy_percentage = prediction.get("accuracy_percentage")
        if accuracy_percentage is None:
            score = float(prediction.get("score", 0.0))
            # Alternate 500-draw methods return score as 0..1 probability.
            accuracy_percentage = score * 100.0

        return {
            "number": prediction["number"],
            "size": prediction["size"],
            "color": prediction["color"],
            "accuracy": f"{float(accuracy_percentage):.1f}%",
            "accuracy_value": float(accuracy_percentage),
            "method": prediction.get("method"),
            "reasoning": prediction.get("reasoning"),
        }

    def _select_prediction_slots(self, predictions: List[Dict[str, Any]]) -> tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not predictions:
            raise RuntimeError("ProbabilityEngine returned no predictions")

        primary = predictions[0]
        alternative = predictions[1] if len(predictions) > 1 else None
        backup = predictions[2] if len(predictions) > 2 else None
        return primary, alternative, backup
    
    # ==================== PREDICTION GENERATION ====================
    
    def generate_prediction(self) -> Dict[str, Any]:
        """
        Generate complete prediction with all analysis.
        
        Returns:
            Complete prediction dictionary with 5 prediction methods:
            - primary, alternative, backup (from trained model)
            - frequency_only, pattern_filtered (from 500-draw analysis)
        """
        logger.info("Generating prediction...")
        
        predictions = self.probability_engine.get_top_predictions(3)
        primary, alternative, backup = self._select_prediction_slots(predictions)
        logger.info(
            "Prediction slots selected: primary=%s alternative=%s backup=%s",
            primary["number"],
            alternative["number"] if alternative else "None",
            backup["number"] if backup else "None",
        )
        
        # 500-draw analysis predictions
        freq_only = self.probability_engine.get_frequency_only_prediction()
        pattern_filtered = self.probability_engine.get_pattern_filtered_prediction()
        logger.info(
            "Alt predictions: frequency_only=%s (%.1f%%) | pattern_filtered=%s (%.1f%%)",
            freq_only["number"], freq_only["score"] * 100,
            pattern_filtered["number"], pattern_filtered["score"] * 100,
        )
        
        next_period = self._calculate_next_period()
        
        prediction: Dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "current_period": self.period,
            "next_period": next_period,
            "draws_used": len(self.draws),
            "scoring_profile": "hierarchical_color_size_number_v3",
            "learning_weights": self.probability_engine.weights,
            "primary_prediction": self._prediction_entry(primary),
            "alternative_prediction": self._prediction_entry(alternative) if alternative else None,
            "backup_prediction": self._prediction_entry(backup) if backup else None,
            "strong_possibility": self._prediction_entry(backup) if backup else None,
            "alt_predictions": {
                "frequency_only_500": self._prediction_entry(freq_only),
                "pattern_filtered_500": self._prediction_entry(pattern_filtered)
            },
            "trend_analysis": self._generate_trend_analysis(),
            "probability_explanation": self._generate_probability_explanation(primary["number"]),
            "summary": self._generate_summary(predictions),
            "all_five_methods": {
                "trained_model": [
                    primary["number"],
                    alternative["number"] if alternative else None,
                    backup["number"] if backup else None
                ],
                "frequency_500": freq_only["number"],
                "pattern_filtered_500": pattern_filtered["number"]
            }
        }
        
        logger.info(f"Prediction generated successfully")
        return prediction
    
    # ==================== TREND ANALYSIS ====================
    
    def _generate_trend_analysis(self) -> Dict[str, str]:
        """Generate detailed trend analysis."""
        size_pattern = self.patterns.get("size_patterns", {})
        color_pattern = self.patterns.get("color_patterns", {})
        cycles = self.patterns.get("cycles", [])
        
        analysis = {
            "size_pattern": self._format_size_pattern(size_pattern),
            "color_pattern": self._format_color_pattern(color_pattern),
            "active_streak": self._format_active_streak(size_pattern),
            "detected_cycle": self._format_detected_cycle(cycles)
        }
        
        return analysis
    
    def _format_size_pattern(self, pattern: Dict[str, Any]) -> str:
        """Format size pattern for display."""
        pattern_type = pattern.get("pattern_type")
        if pattern_type:
            strength = float(pattern.get("pattern_strength", 0.0))
            
            if pattern_type == "Streak":
                streak = pattern.get("current_streak", {})
                streak_type = streak.get("type", "Unknown")
                streak_length = streak.get("length", 0)
                return (f"{pattern_type} Pattern - {streak_type} x {streak_length} "
                       f"(Strength: {strength:.0%})")
            else:
                return f"{pattern_type} Pattern (Strength: {strength:.0%})"
        
        return "No strong pattern detected"
    
    def _format_color_pattern(self, pattern: Dict[str, Any]) -> str:
        """Format color pattern for display."""
        pattern_type = pattern.get("pattern_type")
        if pattern_type:
            strength = float(pattern.get("pattern_strength", 0.0))
            return f"{pattern_type} (Strength: {strength:.0%})"
        
        dominant = pattern.get("dominant_color", {})
        if dominant.get("color"):
            return f"Dominant: {dominant['color']} ({float(dominant.get('percentage', 0.0)):.1f}%)"
        
        return "No pattern detected"
    
    def _format_active_streak(self, size_pattern: Dict[str, Any]) -> str:
        """Format active streak information."""
        streak = size_pattern.get("current_streak", {})
        streak_length = int(streak.get("length", 0))
        
        if streak_length >= 2:
            direction = "May reverse" if streak_length >= Config.MIN_STREAK_LENGTH else "May continue"
            return f"{streak.get('type', 'Unknown')} x {streak_length} - {direction}"
        
        return "No active streak"
    
    def _format_detected_cycle(self, cycles: List[Dict[str, Any]]) -> str:
        """Format detected cycle information."""
        if cycles:
            cycle = max(cycles, key=lambda item: float(item.get("strength", 0.0)))
            strength = float(cycle.get("strength", 0.0))
            cycle_length = cycle.get("cycle_length")
            if strength > 0.5 and cycle_length is not None:
                return f"{cycle_length}-round cycle (Strength: {strength:.0%})"
        
        return "No cycle detected"
    
    # ==================== PROBABILITY EXPLANATION ====================
    
    def _generate_probability_explanation(self, number: int) -> str:
        """Generate explanation for why a number was predicted."""
        explanation = self.probability_engine.explain_prediction(number)
        
        factors: List[str] = []
        
        if explanation["trend_weight"] > 0.20:
            factors.append(f"Trend analysis ({explanation['trend_weight']:.2%})")
        
        if explanation["cycle_weight"] > 0.20:
            factors.append(f"Cycle detection ({explanation['cycle_weight']:.2%})")
        
        if explanation["streak_weight"] > 0.20:
            factors.append(f"Streak reversal ({explanation['streak_weight']:.2%})")

        if explanation["sequence_weight"] > 0.20:
            factors.append(f"Sequence learner ({explanation['sequence_weight']:.2%})")
        
        if not factors:
            factors.append(f"Comprehensive analysis (Total: {explanation['total_score']:.2%})")
        
        return "Based on: " + ", ".join(factors)
    
    # ==================== SUMMARY ====================
    
    def _generate_summary(self, predictions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate summary with best bets."""
        primary, alternative, backup = self._select_prediction_slots(predictions)
        alt = alternative or primary
        backup_pick = backup or alt
        return {
            "best_bet": f"NUMBER {primary['number']} ({primary['color']}, {primary['size']})",
            "alternative_bet": f"NUMBER {alt['number']} ({alt['color']}, {alt['size']})",
            "backup_bet": f"NUMBER {backup_pick['number']} ({backup_pick['color']}, {backup_pick['size']})",
            "combined_strategy": (
                f"Play {primary['number']} with "
                f"{primary['accuracy_percentage']:.0f}% "
                f"confidence. Backup with {alt['number']} if needed."
            )
        }
    
    # ==================== UTILITIES ====================
    
    def _calculate_next_period(self) -> str:
        """Calculate next period ID."""
        if not self.period:
            return "UNKNOWN"
        
        period_str = str(self.period)
        try:
            period_int = int(period_str)
            return str(period_int + 1)
        except ValueError:
            match = re.search(r"(\d+)$", period_str)
            if not match:
                return period_str

            suffix = match.group(1)
            prefix = period_str[:-len(suffix)]
            next_suffix = str(int(suffix) + 1).zfill(len(suffix))
            return f"{prefix}{next_suffix}"
    
    def format_output(self, prediction: Dict[str, Any]) -> str:
        """
        Format prediction for console display.
        
        Args:
            prediction: Prediction dictionary from generate_prediction()
            
        Returns:
            Formatted string for display
        """
        output: List[str] = []
        output.append("\n" + "="*60)
        output.append("         BDG GAME PREDICTION ENGINE")
        output.append("="*60 + "\n")
        
        # Next Period
        output.append(f"Next Period: {prediction['next_period']}\n")
        
        # Primary Prediction
        output.append(f"{self.PRIMARY_LABEL.upper()} PREDICTION")
        output.append("-" * self.SECTION_WIDTH)
        primary = prediction["primary_prediction"]
        output.append(f"Number:   {primary['number']}")
        output.append(f"Size:     {primary['size']}")
        output.append(f"Color:    {primary['color']}")
        output.append(f"Accuracy: {primary['accuracy']}\n")
        
        if prediction["alternative_prediction"]:
            output.append(f"{self.ALTERNATIVE_LABEL.upper()} PREDICTION")
            output.append("-" * self.SECTION_WIDTH)
            alt = prediction["alternative_prediction"]
            output.append(f"Number:   {alt['number']}")
            output.append(f"Size:     {alt['size']}")
            output.append(f"Color:    {alt['color']}")
            output.append(f"Accuracy: {alt['accuracy']}\n")
        
        backup_prediction = prediction.get("backup_prediction") or prediction.get("strong_possibility")
        if backup_prediction:
            output.append(f"{self.BACKUP_LABEL.upper()} PREDICTION")
            output.append("-" * self.SECTION_WIDTH)
            output.append(f"Number:   {backup_prediction['number']}")
            output.append(f"Size:     {backup_prediction['size']}")
            output.append(f"Color:    {backup_prediction['color']}")
            output.append(f"Accuracy: {backup_prediction['accuracy']}\n")
        
        # 500-Draw Analysis Predictions
        alt_preds = prediction.get("alt_predictions", {})
        if alt_preds:
            output.append("="*60)
            output.append("ALT PREDICTIONS (500-DRAW ANALYSIS)")
            output.append("="*60 + "\n")
            
            freq_only = alt_preds.get("frequency_only_500")
            if freq_only:
                output.append("FREQUENCY-ONLY (Pure 500-draw count)")
                output.append("-" * self.SECTION_WIDTH)
                output.append(f"Number:   {freq_only['number']}")
                output.append(f"Size:     {freq_only['size']}")
                output.append(f"Color:    {freq_only['color']}")
                output.append(f"Score:    {freq_only['accuracy']}")
                output.append(f"Method:   {freq_only.get('reasoning', 'Baseline')}\n")
            
            pattern_filt = alt_preds.get("pattern_filtered_500")
            if pattern_filt:
                output.append("PATTERN-FILTERED (Frequency + Detected Patterns)")
                output.append("-" * self.SECTION_WIDTH)
                output.append(f"Number:   {pattern_filt['number']}")
                output.append(f"Size:     {pattern_filt['size']}")
                output.append(f"Color:    {pattern_filt['color']}")
                output.append(f"Score:    {pattern_filt['accuracy']}")
                output.append(f"Method:   {pattern_filt.get('reasoning', 'Pattern match')}\n")
        
        output.append("TREND ANALYSIS")
        output.append("-" * self.SECTION_WIDTH)
        trends = prediction["trend_analysis"]
        output.append(f"Size Pattern:    {trends['size_pattern']}")
        output.append(f"Color Pattern:   {trends['color_pattern']}")
        output.append(f"Active Streak:   {trends['active_streak']}")
        output.append(f"Detected Cycle:  {trends['detected_cycle']}\n")
        
        output.append("PROBABILITY EXPLANATION")
        output.append("-" * self.SECTION_WIDTH)
        output.append(prediction["probability_explanation"] + "\n")
        
        output.append("FINAL SUMMARY")
        output.append("-" * self.SECTION_WIDTH)
        summary = prediction["summary"]
        output.append(f"Best Bet:           {summary['best_bet']}")
        output.append(f"Alternative Bet:    {summary['alternative_bet']}")
        output.append(f"Backup Bet:         {summary['backup_bet']}\n")
        output.append(f"Strategy:           {summary['combined_strategy']}")
        
        output.append("\n" + "="*60)
        output.append(f"Generated: {prediction['timestamp']}")
        output.append("="*60 + "\n")
        
        return "\n".join(output)
    
    def print_prediction(self) -> Dict[str, Any]:
        """Generate and print prediction to console."""
        prediction = self.generate_prediction()
        formatted = self.format_output(prediction)
        print(formatted)
        return prediction
    
    def get_quick_prediction(self) -> Dict[str, Any]:
        """Get quick prediction summary (useful for automation)."""
        prediction = self.generate_prediction()
        alt = prediction.get("alternative_prediction") or prediction["primary_prediction"]
        backup = (
            prediction.get("backup_prediction")
            or prediction.get("strong_possibility")
            or prediction["primary_prediction"]
        )
        return {
            "next_period":       prediction["next_period"],
            "best_number":       prediction["primary_prediction"]["number"],
            "best_size":         prediction["primary_prediction"]["size"],
            "best_color":        prediction["primary_prediction"]["color"],
            "confidence":        prediction["primary_prediction"]["accuracy"],
            "confidence_value":  prediction["primary_prediction"].get("accuracy_value", 0.0),
            "alternative_number": alt["number"],
            "backup_number":     backup["number"],
        }


__all__ = ["Predictor"]
