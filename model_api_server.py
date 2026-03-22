import sys
import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add the project directory to sys.path to import modules
project_dir = os.path.join(os.getcwd(), "bdg_predictor")
sys.path.append(project_dir)

from data_fetcher import DataFetcher
from pattern_detector import PatternDetector
from probability_engine import ProbabilityEngine
from probability_engine import ProbabilityEngine
from config import Config
from firebase_client import fetch_firestore_history, get_hit_miss_summary

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Native CORS support as per Rule 3

# Helper to fetch draws and handle API/merge
def get_draw_data(game, page_size=20):
    # 1. Fetch from Live API
    fetcher = DataFetcher()
    payload = fetcher.fetch_past_draws(game_code=game, page_size=page_size)
    draws_data = fetcher.extract_draws(payload or {})
    
    # 2. Optionally merge with Firestore if we want high-depth
    # For speed/ticker purposes, live API is enough. 
    # For prediction, we use Firestore.
    return draws_data, payload

@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        game = request.args.get('game', Config.GAME_CODE)
        page_size = request.args.get('pageSize', 500)
        logger.info(f"Proxying history request for {game}...")
        
        draws, payload = get_draw_data(game, int(page_size))
        if not payload:
            return jsonify({"status": "error", "message": "Failed to fetch history"}), 500
            
        return jsonify(payload)
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/draw/history', methods=['GET'])
def get_draw_history_alias():
    # Alias for AR Predictor compatibility
    return get_history()

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns the globally aggregated hit/miss summary from Firebase."""
    try:
        game = request.args.get('game', Config.GAME_CODE)
        logger.info(f"Fetching global stats for {game}...")
        summary = get_hit_miss_summary(game)
        return jsonify({"status": "success", "data": summary})
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/advanced/predict', methods=['GET'])
def predict():
    try:
        game = request.args.get('game', Config.GAME_CODE)
        logger.info(f"Generating advanced prediction for {game}...")
        
        # 1. Fetch historical draws (5000 from Firestore + 10 from API)
        # Firestore history
        numbers = fetch_firestore_history(limit=5000)
        
        # Live history from API to ensure we are up to date
        fetcher = DataFetcher()
        payload = fetcher.fetch_past_draws(game_code=game)
        draws_data = fetcher.extract_draws(payload or {})
        
        if not draws_data and not numbers:
            return jsonify({"status": "error", "message": "Failed to fetch any data"}), 500
            
        latest_period = draws_data[0]['period'] if draws_data else "Unknown"
        
        # Merge logic
        if not numbers:
            numbers = [d['number'] for d in draws_data]
        elif draws_data:
            api_numbers = [d['number'] for d in draws_data]
            if api_numbers[0] != numbers[0]:
                numbers = api_numbers + numbers
        
        # 2. Run Advanced Analysis
        detector = PatternDetector(numbers)
        patterns = detector.analyze_all_patterns()
        
        engine = ProbabilityEngine(numbers, patterns)
        analysis = engine.get_probability_analysis()
        
        # 3. Format Response as expected by index.html
        # index.html expects data.top3 list
        response = {
            "status": "success",
            "period": latest_period,
            "next_period": str(int(latest_period) + 1 if latest_period != "Unknown" else "Unknown"),
            "model": "LSTM+Markov (Advanced)",
            "top3": [
                {
                    "number": p["number"],
                    "size": p["size"],
                    "color": p["color"],
                    "prob": p["confidence"]
                } for p in analysis["top_predictions"]
            ],
            "patterns": patterns
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "engine": "bdg_predictor_v12"})

if __name__ == '__main__':
    # Start the server on 8787 as per rule 1 & 5
    print("Starting BDG Model API Server on port 8787...")
    app.run(host='0.0.0.0', port=8787, debug=False)
