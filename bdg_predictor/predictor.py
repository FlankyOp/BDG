"""
Predictor Module
Main prediction orchestrator combining all analysis components.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from pattern_detector import PatternDetector
from probability_engine import ProbabilityEngine

logger = logging.getLogger(__name__)


class Predictor:
    """Main predictor orchestrator."""
    
    def __init__(self, draws: List[int], period: Optional[str] = None, weight_profile: Optional[Dict[str, float]] = None):
        """
        Initialize predictor.
        
        Args:
            draws: List of recent draw numbers
            period: Current period ID
            weight_profile: Optional adaptive weight profile
        """
        self.draws = draws
        self.period = period
        self.timestamp = datetime.now()
        self.weight_profile = weight_profile
        
        # Initialize components
        self.pattern_detector = PatternDetector(draws)
        self.patterns = self.pattern_detector.analyze_all_patterns()
        self.probability_engine = ProbabilityEngine(draws, self.patterns, weight_profile=weight_profile)
    
    # ==================== PREDICTION GENERATION ====================
    
    def generate_prediction(self) -> Dict[str, Any]:
        """
        Generate complete prediction with all analysis.
        
        Returns:
            Complete prediction dictionary
        """
        logger.info("Generating prediction...")
        
        predictions = self.probability_engine.get_top_predictions(3)
        
        # Determine next period
        next_period = self._calculate_next_period()
        
        prediction: Dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "current_period": self.period,
            "next_period": next_period,
            "draws_used": len(self.draws),
            "scoring_profile": "hierarchical_color_size_number_v3",
            "learning_weights": self.probability_engine.weights,
            "primary_prediction": {
                "number": predictions[0]["number"],
                "size": predictions[0]["size"],
                "color": predictions[0]["color"],
                "accuracy": f"{predictions[0]['accuracy_percentage']:.1f}%"
            },
            "alternative_prediction": {
                "number": predictions[1]["number"],
                "size": predictions[1]["size"],
                "color": predictions[1]["color"],
                "accuracy": f"{predictions[1]['accuracy_percentage']:.1f}%"
            } if len(predictions) > 1 else None,
            "strong_possibility": {
                "number": predictions[2]["number"],
                "size": predictions[2]["size"],
                "color": predictions[2]["color"],
                "accuracy": f"{predictions[2]['accuracy_percentage']:.1f}%"
            } if len(predictions) > 2 else None,
            "trend_analysis": self._generate_trend_analysis(),
            "probability_explanation": self._generate_probability_explanation(predictions[0]["number"]),
            "summary": self._generate_summary(predictions)
        }
        
        logger.info(f"Prediction generated successfully")
        return prediction
    
    # ==================== TREND ANALYSIS ====================
    
    def _generate_trend_analysis(self) -> Dict[str, str]:
        """Generate detailed trend analysis."""
        size_pattern = self.patterns["size_patterns"]
        color_pattern = self.patterns["color_patterns"]
        cycles = self.patterns["cycles"]
        
        analysis = {
            "size_pattern": self._format_size_pattern(size_pattern),
            "color_pattern": self._format_color_pattern(color_pattern),
            "active_streak": self._format_active_streak(size_pattern),
            "detected_cycle": self._format_detected_cycle(cycles)
        }
        
        return analysis
    
    def _format_size_pattern(self, pattern: Dict[str, Any]) -> str:
        """Format size pattern for display."""
        if pattern["pattern_type"]:
            strength = pattern["pattern_strength"]
            pattern_type = pattern["pattern_type"]
            
            if pattern_type == "Streak":
                streak = pattern["current_streak"]
                return (f"{pattern_type} Pattern - {streak['type']} x {streak['length']} "
                       f"(Strength: {strength:.0%})")
            else:
                return f"{pattern_type} Pattern (Strength: {strength:.0%})"
        
        return "No strong pattern detected"
    
    def _format_color_pattern(self, pattern: Dict[str, Any]) -> str:
        """Format color pattern for display."""
        if pattern["pattern_type"]:
            strength = pattern["pattern_strength"]
            return f"{pattern['pattern_type']} (Strength: {strength:.0%})"
        
        dominant = pattern["dominant_color"]
        if dominant["color"]:
            return f"Dominant: {dominant['color']} ({dominant['percentage']:.1f}%)"
        
        return "No pattern detected"
    
    def _format_active_streak(self, size_pattern: Dict[str, Any]) -> str:
        """Format active streak information."""
        streak = size_pattern["current_streak"]
        
        if streak["length"] >= 2:
            direction = "May reverse" if streak["length"] >= 3 else "May continue"
            return f"{streak['type']} x {streak['length']} - {direction}"
        
        return "No active streak"
    
    def _format_detected_cycle(self, cycles: List[Dict[str, Any]]) -> str:
        """Format detected cycle information."""
        if cycles and cycles[0]["strength"] > 0.5:
            cycle = cycles[0]
            return f"{cycle['cycle_length']}-round cycle (Strength: {cycle['strength']:.0%})"
        
        return "No cycle detected"
    
    # ==================== PROBABILITY EXPLANATION ====================
    
    def _generate_probability_explanation(self, number: int) -> str:
        """Generate explanation for why a number was predicted."""
        explanation = self.probability_engine.explain_prediction(number)
        
        factors: List[str] = []
        
        if float(explanation["trend_weight"].strip("%")) > 20:
            factors.append(f"Trend analysis ({explanation['trend_weight']})")
        
        if float(explanation["cycle_weight"].strip("%")) > 20:
            factors.append(f"Cycle detection ({explanation['cycle_weight']})")
        
        if float(explanation["streak_weight"].strip("%")) > 20:
            factors.append(f"Streak reversal ({explanation['streak_weight']})")
        
        if not factors:
            factors.append(f"Comprehensive analysis (Total: {explanation['total_score']})")
        
        return "Based on: " + ", ".join(factors)
    
    # ==================== SUMMARY ====================
    
    def _generate_summary(self, predictions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate summary with best bets."""
        alt    = predictions[1] if len(predictions) > 1 else predictions[0]
        backup = predictions[2] if len(predictions) > 2 else predictions[0]
        return {
            "best_bet": f"NUMBER {predictions[0]['number']} ({predictions[0]['color']}, {predictions[0]['size']})",
            "alternative_bet": f"NUMBER {alt['number']} ({alt['color']}, {alt['size']})",
            "backup_bet": f"NUMBER {backup['number']} ({backup['color']}, {backup['size']})",
            "combined_strategy": (
                f"Play {predictions[0]['number']} with "
                f"{predictions[0]['accuracy_percentage']:.0f}% "
                f"confidence. Backup with {alt['number']} if needed."
            )
        }
    
    # ==================== UTILITIES ====================
    
    def _calculate_next_period(self) -> str:
        """Calculate next period ID."""
        if not self.period:
            return "UNKNOWN"
        
        try:
            period_int = int(self.period)
            return str(period_int + 1)
        except ValueError:
            return self.period
    
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
        output.append("PRIMARY PREDICTION")
        output.append("-" * 40)
        primary = prediction["primary_prediction"]
        output.append(f"Number:   {primary['number']}")
        output.append(f"Size:     {primary['size']}")
        output.append(f"Color:    {primary['color']}")
        output.append(f"Accuracy: {primary['accuracy']}\n")
        
        # Alternative Prediction
        if prediction["alternative_prediction"]:
            output.append("ALTERNATIVE PREDICTION")
            output.append("-" * 40)
            alt = prediction["alternative_prediction"]
            output.append(f"Number:   {alt['number']}")
            output.append(f"Size:     {alt['size']}")
            output.append(f"Color:    {alt['color']}")
            output.append(f"Accuracy: {alt['accuracy']}\n")
        
        # Strong Possibility
        if prediction["strong_possibility"]:
            output.append("STRONG POSSIBILITY")
            output.append("-" * 40)
            strong = prediction["strong_possibility"]
            output.append(f"Number:   {strong['number']}")
            output.append(f"Size:     {strong['size']}")
            output.append(f"Color:    {strong['color']}")
            output.append(f"Accuracy: {strong['accuracy']}\n")
        
        # Trend Analysis
        output.append("TREND ANALYSIS")
        output.append("-" * 40)
        trends = prediction["trend_analysis"]
        output.append(f"Size Pattern:    {trends['size_pattern']}")
        output.append(f"Color Pattern:   {trends['color_pattern']}")
        output.append(f"Active Streak:   {trends['active_streak']}")
        output.append(f"Detected Cycle:  {trends['detected_cycle']}\n")
        
        # Probability Explanation
        output.append("PROBABILITY EXPLANATION")
        output.append("-" * 40)
        output.append(prediction["probability_explanation"] + "\n")
        
        # Summary
        output.append("FINAL SUMMARY")
        output.append("-" * 40)
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
        alt    = prediction["alternative_prediction"] or prediction["primary_prediction"]
        backup = prediction["strong_possibility"]     or prediction["primary_prediction"]
        return {
            "next_period":       prediction["next_period"],
            "best_number":       prediction["primary_prediction"]["number"],
            "best_size":         prediction["primary_prediction"]["size"],
            "best_color":        prediction["primary_prediction"]["color"],
            "confidence":        prediction["primary_prediction"]["accuracy"],
            "alternative_number": alt["number"],
            "backup_number":     backup["number"],
        }


__all__ = ["Predictor"]
