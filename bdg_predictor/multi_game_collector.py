"""
Multi-Game Mode Collector
Automatically collects data from all 4 game modes (30S, 1M, 3M, 5M)
and stores to Firebase without manual switching.

Deploy to Railway.app for 24/7 collection without PC running.
"""

import logging
import threading
import time
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

import firebase_client
from data_fetcher import DataFetcher
from pattern_detector import ColorMapper, SizeMapper
from config import Config

logger = logging.getLogger(__name__)

# All 4 game modes to poll
GAME_MODES = [
    "WinGo_30S",
    "WinGo_1M",
    "WinGo_3M",
    "WinGo_5M",
]

# Polling intervals (seconds) - match game duration
POLLING_INTERVALS = {
    "WinGo_30S": 30,
    "WinGo_1M": 60,
    "WinGo_3M": 180,
    "WinGo_5M": 300,
}


class GameModeCollector:
    """Collects data from a single game mode and stores to Firebase."""
    
    def __init__(self, game_code: str):
        self.game_code = game_code
        self.interval = POLLING_INTERVALS.get(game_code, 60)
        self.data_fetcher = DataFetcher()
        self.last_period = None
        self.running = False
        logger.info(f"[{game_code}] Collector initialized (interval={self.interval}s)")
    
    def _fetch_latest_draw(self) -> Optional[Dict[str, Any]]:
        """Fetch latest draw for this game mode."""
        try:
            data = self.data_fetcher.fetch_past_draws(game_code=self.game_code, page_size=1)
            if not data:
                return None
            
            rows = self.data_fetcher.extract_draws(data)
            return rows[0] if rows else None
        except Exception as e:
            logger.warning(f"[{self.game_code}] Fetch failed: {e}")
            return None
    
    def _store_to_firebase(self, draw_row: Dict[str, Any]) -> None:
        """Store draw to Firebase with game_code."""
        try:
            number = int(draw_row.get("number", -1))
            if number < 0 or number > 9:
                logger.warning(f"[{self.game_code}] Invalid number: {number}")
                return
            
            period = str(draw_row.get("period", ""))
            if not period:
                logger.warning(f"[{self.game_code}] No period found")
                return
            
            # Store to Firestore with game_code metadata
            firebase_client.push_draw_to_firestore(
                period=period,
                number=number,
                color=ColorMapper.get_color(number),
                size=SizeMapper.get_size(number),
                game_code=self.game_code,
            )
            logger.info(f"[{self.game_code}] Stored: period={period}, number={number}")
        except Exception as e:
            logger.error(f"[{self.game_code}] Firebase store failed: {e}")
    
    def collect(self) -> None:
        """Poll and store one draw."""
        draw = self._fetch_latest_draw()
        if not draw:
            return
        
        period = draw.get("period")
        if period == self.last_period:
            # Same period as last poll, skip
            return
        
        self.last_period = period
        self._store_to_firebase(draw)
    
    def run(self) -> None:
        """Continuous polling loop for this game mode."""
        self.running = True
        logger.info(f"[{self.game_code}] Polling started (every {self.interval}s)")
        
        while self.running:
            try:
                self.collect()
            except Exception as e:
                logger.error(f"[{self.game_code}] Collection error: {e}")
            
            time.sleep(self.interval)
    
    def stop(self) -> None:
        """Stop polling."""
        self.running = False
        logger.info(f"[{self.game_code}] Polling stopped")


class MultiGameCollector:
    """Manages collection from all game modes in parallel threads."""
    
    def __init__(self):
        self.collectors: Dict[str, GameModeCollector] = {
            game_code: GameModeCollector(game_code)
            for game_code in GAME_MODES
        }
        self.threads: Dict[str, threading.Thread] = {}
        logger.info("MultiGameCollector initialized")
    
    def start_all(self) -> None:
        """Start polling all game modes in parallel."""
        logger.info("=" * 60)
        logger.info("MULTI-GAME COLLECTOR STARTED")
        logger.info("=" * 60)
        logger.info(f"Polling {len(GAME_MODES)} game modes:")
        for game_code in GAME_MODES:
            logger.info(f"  • {game_code} (every {POLLING_INTERVALS[game_code]}s)")
        logger.info("=" * 60)
        
        for game_code, collector in self.collectors.items():
            thread = threading.Thread(target=collector.run, daemon=True)
            thread.start()
            self.threads[game_code] = thread
            logger.info(f"[{game_code}] Thread started")
        
        logger.info("All collectors running! Data accumulating in Firebase...")
    
    def stop_all(self) -> None:
        """Stop all collectors."""
        logger.info("Stopping all collectors...")
        for collector in self.collectors.values():
            collector.stop()
        
        for thread in self.threads.values():
            thread.join(timeout=5)
        
        logger.info("All collectors stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all collectors."""
        return {
            game_code: {
                "running": collector.running,
                "last_period": collector.last_period,
                "interval": collector.interval,
            }
            for game_code, collector in self.collectors.items()
        }


def main():
    """Start multi-game collection."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Initialize Firebase
    if not firebase_client.init_firebase():
        logger.error("Firebase initialization failed!")
        return
    
    logger.info("Firebase initialized successfully")
    
    # Start all collectors
    collector = MultiGameCollector()
    collector.start_all()
    
    try:
        # Keep running
        while True:
            time.sleep(60)
            status = collector.get_status()
            logger.info(f"Status: {status}")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        collector.stop_all()


if __name__ == "__main__":
    main()
