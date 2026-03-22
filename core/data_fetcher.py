import logging
import random
from typing import Any, Dict, List, Optional, cast
import requests
from .config import Config

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, timeout: int = Config.API_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_past_draws(self, game_code: str = Config.GAME_CODE, page_size: int = 500) -> Optional[Dict[str, Any]]:
        url = f"{Config.API_BASE_URL}/WinGo/{game_code}/GetHistoryIssuePage.json?pageSize={page_size}&pageNo=1"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.ok:
                return response.json()
        except Exception as e:
            logger.debug(f"Fetch failed: {e}")
        return None

    def extract_draws(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = []
        rows = payload.get("data", {}).get("list", []) or payload.get("list", [])
        for row in rows:
            issue = row.get("issueNumber") or row.get("period")
            number = row.get("number")
            color = row.get("color")
            if issue and number is not None:
                result.append({"period": str(issue), "number": int(number), "color": str(color or "")})
        return result

def create_sample_data(length: int = 120, seed: int = 42) -> List[int]:
    rng = random.Random(seed)
    return [rng.randint(0, 9) for _ in range(max(10, length))]
