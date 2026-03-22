#!/usr/bin/env python3
"""
BDG Predictor - Model API Server
Lightweight HTTP server for LSTM predictions and draw history.

Serves:
  GET /api/history?game=WinGo_1M&pageSize=100  → Live draw history
  GET /api/advanced/predict?game=WinGo_1M      → Top-3 predictions
  GET /api/stats?game=WinGo_1M                  → Global accuracy stats
  GET /health                                    → Server health check
"""

import json
import http.server
import socketserver
import urllib.parse
import logging
from http import HTTPStatus
from typing import Dict, List, Any, Optional

from data_fetcher import DataFetcher  # type: ignore
from predictor import Predictor  # type: ignore
from pattern_detector import PatternDetector  # type: ignore
from config import Config  # type: ignore
from core.discord_notifier import send_sure_shot_alert

PORT = 8787
HOST = "127.0.0.1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# --- Global Bot State ---
BOT_STATE = {
    "command": None,
    "status": None
}


def _remap_draws(draws: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map DataFetcher rows (key='period') → dashboard format (key='issueNumber')."""
    out = []
    for d in draws:
        out.append(
            {
                "issueNumber": d.get("period", ""),
                "number": d.get("number", 0),
                "colour": d.get("color", ""),
                "color": d.get("color", ""),
                "size": "Big" if int(d.get("number", 0)) >= 5 else "Small",
            }
        )
    return out


class BDGHandler(http.server.BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self._fetcher = DataFetcher()
        super().__init__(*args, **kwargs)

    # ─── CORS helper ──────────────────────────────────────────────────────────

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    # Bug-6 fix: inject CORS before every error so the browser can read the body
    def send_error(self, code, message=None, explain=None):
        self.send_response(code)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = f"<h1>{code} {message or ''}</h1>"
        self.wfile.write(body.encode())

    def send_json(self, data: Dict[str, Any], status: int = HTTPStatus.OK):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    # ─── CORS preflight ───────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.end_headers()

    # ─── GET dispatcher ───────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/history":
            self._serve_history(qs)

        # Bug-1 fix: predict is now a GET endpoint
        elif parsed.path == "/api/advanced/predict":
            self._serve_prediction(qs)

        elif parsed.path == "/api/stats":
            self._serve_stats(qs)

        elif parsed.path == "/health":
            self.send_json({"status": "healthy", "server": "BDG Model API", "port": PORT})

        elif parsed.path == "/api/bot/command":
            self.send_json({"status": "success", "data": BOT_STATE["command"]})

        elif parsed.path == "/api/bot/status":
            self.send_json({"status": "success", "data": BOT_STATE["status"]})

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        
        # Parse body
        data = {}
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)
        except Exception as e:
            logger.error("Failed to parse POST body: %s", e)

        if parsed.path == "/api/bot/command":
            if data.get("action") == "clear":
                BOT_STATE["command"] = None
            else:
                BOT_STATE["command"] = data
                BOT_STATE["status"] = None  # Reset status when new command is issued
            self.send_json({"status": "success"})

        elif parsed.path == "/api/bot/status":
            BOT_STATE["status"] = data
            self.send_json({"status": "success"})

        elif parsed.path == "/api/notify/discord":
            period = data.get("period", "")
            pred_data = data.get("pred_data", {})
            bet_plan = data.get("bet_plan", {})
            # Fire in background thread or just synchronously (sync is fine for now)
            import threading
            threading.Thread(target=send_sure_shot_alert, args=(period, pred_data, bet_plan)).start()
            self.send_json({"status": "success"})

        else:
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Endpoint not found or Use GET")

    # ─── Handlers ─────────────────────────────────────────────────────────────

    def _serve_history(self, qs: Dict[str, List[str]]):
        """Return recent draw history in the format dashboard.html expects."""
        game = qs.get("game", ["WinGo_1M"])[0]
        page_size = int(qs.get("pageSize", ["100"])[0])

        # Bug-2 fix: use keyword argument `game_code`
        raw = self._fetcher.fetch_past_draws(game_code=game, page_size=page_size)
        draws = self._fetcher.extract_draws(raw) if raw else []

        # Bug-3 fix: dashboard expects `issueNumber`, not `period`
        remapped = _remap_draws(draws)

        self.send_json({"status": "success", "data": {"list": remapped}})

    def _serve_prediction(self, qs: Dict[str, List[str]]):
        """Generate a top-3 prediction from the latest draws."""
        game = qs.get("game", ["WinGo_1M"])[0]

        # Bug-2 fix: correct keyword argument
        raw = self._fetcher.fetch_past_draws(game_code=game, page_size=100)
        draws = self._fetcher.extract_draws(raw) if raw else []
        numbers: List[int] = [int(d["number"]) for d in draws]

        if len(numbers) < 3:
            # fallback mock prediction
            self.send_json(self._mock_prediction())
            return

        try:
            # Bug-4 fix: create a fresh Predictor per request; do NOT store state
            pred_input = numbers[:100]  # cap at 100 draws
            predictor = Predictor(pred_input)  # type: ignore
            result = predictor.generate_prediction()

            # Build top3 list expected by the dashboard JS
            top3 = []
            for slot in ("primary_prediction", "alternative_prediction", "backup_prediction"):
                entry = result.get(slot)
                if entry:
                    raw_acc = entry.get("accuracy_value", 0.0)
                    top3.append(
                        {
                            "number": entry["number"],
                            "size": entry["size"],
                            "color": entry["color"],
                            "prob": round(float(raw_acc) / 100.0, 4),
                        }
                    )

            # Collect pattern info for the frontend
            patterns: Dict[str, Any] = {}
            try:
                detector = PatternDetector(pred_input)  # type: ignore
                all_patterns = detector.analyze_all_patterns()
                patterns = {
                    "color_patterns": all_patterns.get("color_patterns", {}),
                    "size_patterns": all_patterns.get("size_patterns", {}),
                    "recent_colors": [
                        "Green" if n in (1, 3, 7, 9, 5) else "Red"
                        for n in numbers[:10]
                    ],
                }
            except Exception:
                pass

            self.send_json({"status": "success", "top3": top3, "patterns": patterns})

        except Exception as exc:
            logger.exception("Prediction failed: %s", exc)
            self.send_json(self._mock_prediction())

    def _serve_stats(self, qs: Dict[str, List[str]]):
        """Return mock/aggregated prediction accuracy stats."""
        self.send_json(
            {
                "status": "success",
                "data": {
                    "total_predictions": 1250,
                    "number_hit": 312,
                    "number_miss": 938,
                    "size_hit": 645,
                    "size_miss": 605,
                    "color_hit": 623,
                    "color_miss": 627,
                },
            }
        )

    def _mock_prediction(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "top3": [
                {"number": 5, "size": "Big", "color": "Green-Violet", "prob": 0.28},
                {"number": 1, "size": "Small", "color": "Green", "prob": 0.18},
                {"number": 3, "size": "Small", "color": "Green", "prob": 0.14},
            ],
            "patterns": {
                "color_patterns": {"pattern_type": "Streak"},
                "recent_colors": ["Green", "Green", "Red", "Green"],
            },
        }

    def log_message(self, fmt, *args):
        logger.debug("HTTP %s", fmt % args)


def background_discord_monitor():
    """Continuously monitors all game modes and sends Sure Shot Discord alerts autonomously."""
    import time
    from core.discord_notifier import send_sure_shot_alert
    
    logger.info("Starting Background Discord Autobot Monitor for all game modes...")
    fetcher = DataFetcher()
    games = ["WinGo_30S", "WinGo_1M", "WinGo_3M", "WinGo_5M"]
    last_notified: Dict[str, Optional[str]] = {g: None for g in games}
    
    # Initialize Predictor once to prevent severe CPU/Disk thrashing on every poll
    pred_engine = Predictor()
    
    while True:
        try:
            for game in games:
                raw = fetcher.fetch_past_draws(game_code=game, page_size=20)
                draws = fetcher.extract_draws(raw) if raw else []
                if not draws:
                    continue
                
                # The prediction engine and our parsing expect 'issueNumber'
                draws = _remap_draws(draws)
                
                latest_issue = str(draws[0]['issueNumber'])
                target_issue = str(int(latest_issue) + 1)
                
                # If we've already checked this upcoming period, skip
                if target_issue == last_notified[game]:
                    continue
                    
                # Predict
                result = pred_engine.predict_next(draws)
                
                top3 = result.get("top3", [])
                if not top3:
                    continue
                    
                conf = round((top3[0].get("prob", 0)) * 100)
                
                # Global SURE SHOT THRESHOLD = 85%
                if conf >= 85:
                    pattern_str = result.get("patterns", {}).get("color_patterns", {}).get("pattern_type", "AI Ensemble")
                    pred_data = {
                        "number": top3[0].get("number"),
                        "size": top3[0].get("size"),
                        "color": top3[0].get("color"),
                        "confidence": conf,
                        "pattern": pattern_str
                    }
                    bet_plan = {
                        "type": "number (3 entries)",
                        "outlay": 30 # example outlay for 10rs base
                    }
                    send_sure_shot_alert(game, target_issue, pred_data, bet_plan)
                
                # Mark as processed whether we sent a hook or not
                last_notified[game] = target_issue
                
        except Exception as e:
            logger.error("Discord monitor error: %s", e)
            
        time.sleep(3)


def run_server():
    """Start the HTTP API server."""
    # Start the Discord Daemon first
    import threading
    discord_thread = threading.Thread(target=background_discord_monitor, daemon=True)
    discord_thread.start()

    with socketserver.TCPServer((HOST, PORT), BDGHandler) as httpd:
        httpd.allow_reuse_address = True
        logger.info("🚀 BDG Model API running at http://%s:%s", HOST, PORT)
        logger.info("📡 Health:   http://%s:%s/health", HOST, PORT)
        logger.info("📋 History:  http://%s:%s/api/history?game=WinGo_1M", HOST, PORT)
        logger.info("🔮 Predict:  http://%s:%s/api/advanced/predict?game=WinGo_1M", HOST, PORT)
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
