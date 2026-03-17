"""
Data Fetcher Module
Fetches WinGo history data and provides sample fallback draws.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Mapping, cast

import requests
from config import Config

DRAW_BASE = Config.API_BASE_URL


class DataFetcher:
    """HTTP client for WinGo history endpoints."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_past_draws(
        self,
        period: Optional[str] = None,
        game_code: str = "WinGo_1M",
        page_size: int = 500,
    ) -> Optional[Dict[str, Any]]:
        """Fetch history payload with fallback URLs."""
        _ = period  # Reserved for future API variants.
        urls = [
            f"{DRAW_BASE}/WinGo/{game_code}/GetHistoryIssuePage.json?pageSize={page_size}&pageNo=1",
            f"{DRAW_BASE}/WinGo/{game_code}/GetHistoryIssuePage.json",
        ]

        for url in urls:
            try:
                response = self.session.get(url, timeout=self.timeout)
                if not response.ok:
                    continue
                data = response.json()
                if isinstance(data, dict):
                    return cast(Dict[str, Any], data)
            except Exception:
                continue

        return None

    def extract_draws(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract normalized draw rows from API payload."""
        result: List[Dict[str, Any]] = []
        data_block_raw = payload.get("data", {})
        if not isinstance(data_block_raw, dict):
            return result
        data_block = cast(Mapping[str, Any], data_block_raw)
        rows_raw = data_block.get("list", [])
        if not isinstance(rows_raw, list):
            return result
        rows = cast(List[Any], rows_raw)

        for row in rows:
            if not isinstance(row, Mapping):
                continue

            row_map = cast(Mapping[str, Any], row)
            issue = row_map.get("issueNumber") or row_map.get("period")
            number = row_map.get("number")
            color = row_map.get("color")

            if issue is None or number is None:
                continue

            try:
                number_int = int(str(number))
            except (TypeError, ValueError):
                continue

            result.append(
                {
                    "period": str(issue),
                    "number": number_int,
                    "color": str(color) if color is not None else "",
                }
            )

        return result


def create_sample_data(length: int = 120) -> List[int]:
    """Create deterministic pseudo-random draws for offline mode."""
    random.seed(42)
    return [random.randint(0, 9) for _ in range(max(10, length))]
