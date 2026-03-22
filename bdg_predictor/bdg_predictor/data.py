import sys
import os
import json
import logging
import requests

# Add the project directory to sys.path to import modules
project_dir = r"c:\Users\raval\OneDrive\Desktop\BDG\bdg_predictor"
sys.path.append(project_dir)

from data_fetcher import DataFetcher
from pattern_detector import PatternDetector
from probability_engine import ProbabilityEngine
from config import Config

# Configure basic logging to see what's happening
logging.basicConfig(level=logging.INFO)

def run_analysis():
    game_code = "WinGo_1M"
    draw_base = "https://draw.ar-lottery01.com"
    
    print(f"Fetching history for {game_code}...")
    
    all_draws = []
    session = requests.Session()
    
    # Fetch 10 pages of 10 items each = 100 draws
    for page in range(1, 11):
        url = f"{draw_base}/WinGo/{game_code}/GetHistoryIssuePage.json?pageSize=10&pageNo={page}"
        try:
            response = session.get(url, timeout=10)
            if not response.ok:
                print(f"Failed to fetch page {page}: {response.status_code}")
                continue
            
            payload = response.json()
            # Extract draws using the data_fetcher's logic
            fetcher = DataFetcher()
            draws = fetcher.extract_draws(payload)
            
            if not draws:
                print(f"No draws in page {page}")
                break
            
            for d in draws:
                if d['period'] not in {x['period'] for x in all_draws}:
                    all_draws.append(d)
                
            if len(all_draws) >= 100:
                break
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break

    if not all_draws:
        print("No draw data collected. Exiting.")
        return

    print(f"Total draws collected: {len(all_draws)}")
    
    # Sort by period descending (newest first)
    all_draws.sort(key=lambda x: x['period'], reverse=True)
    
    numbers = [d['number'] for d in all_draws]
    latest_period = all_draws[0]['period']
    
    # Pattern Analysis
    detector = PatternDetector(numbers)
    patterns = detector.analyze_all_patterns()
    
    # Probability Engine
    engine = ProbabilityEngine(numbers, patterns)
    analysis = engine.get_probability_analysis()
    
    # Prepare Output
    output = {
        "latest_period": latest_period,
        "next_period": str(int(latest_period) + 1),
        "patterns": {
            "size": patterns.get("size_patterns"),
            "color": patterns.get("color_patterns"),
            "sequence": patterns.get("sequence_patterns", {}).get("source")
        },
        "predictions": analysis
    }
    
    print("\n--- ANALYSIS SUMMARY ---")
    size_p = patterns.get("size_patterns", {})
    print(f"Size Pattern: {size_p.get('pattern_type')} (Strength: {size_p.get('pattern_strength', 0):.2f})")
    
    color_p = patterns.get("color_patterns", {})
    print(f"Color Pattern: {color_p.get('pattern_type')} (Strength: {color_p.get('pattern_strength', 0):.2f})")
    
    print("\n--- TOP PREDICTIONS (Ranked by Confidence) ---")
    for i, pred in enumerate(analysis["top_predictions"]):
        print(f"{i+1}. Number: {pred['number']} | Size: {pred['size']} | Color: {pred['color']} | Confidence: {pred['confidence']:.2%}")
    
    # Save results to a file for later use
    with open(r"c:\Users\raval\OneDrive\Desktop\BDG\analysis_results.json", "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    run_analysis()
