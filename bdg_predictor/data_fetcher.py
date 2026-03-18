"""
Data Fetcher Module
Fetches WinGo history data and provides sample fallback draws.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Mapping, cast

import requests
from config import Config

DRAW_BASE = Config.API_BASE_URL
REQUEST_ATTEMPTS = 2

logger = logging.getLogger(__name__)


class DataFetcher:
    """HTTP client for WinGo history endpoints."""

    def __init__(self, timeout: int = Config.API_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_past_draws(
        self,
        period: Optional[str] = None,
        game_code: str = Config.GAME_CODE,
        page_size: int = 500,
    ) -> Optional[Dict[str, Any]]:
        """Fetch recent history payload with fallback URLs.

        The current upstream endpoint returns a recent history window only.
        `period` is accepted for interface compatibility with callers, but is
        not yet used to query a specific historical period.
        """
        _ = period  # Reserved for future API variants.
        urls = [
            f"{DRAW_BASE}/WinGo/{game_code}/GetHistoryIssuePage.json?pageSize={page_size}&pageNo=1",
            f"{DRAW_BASE}/WinGo/{game_code}/GetHistoryIssuePage.json",
        ]

        for url in urls:
            for attempt in range(1, REQUEST_ATTEMPTS + 1):
                try:
                    response = self.session.get(url, timeout=self.timeout)
                    if not response.ok:
                        logger.debug(
                            "WinGo history request failed: url=%s status=%s attempt=%s",
                            url,
                            response.status_code,
                            attempt,
                        )
                        continue

                    data = response.json()
                    if isinstance(data, dict):
                        return cast(Dict[str, Any], data)

                    logger.debug(
                        "WinGo history request returned non-dict JSON: url=%s attempt=%s",
                        url,
                        attempt,
                    )
                except requests.RequestException as exc:
                    logger.debug("WinGo history request error: url=%s attempt=%s error=%s", url, attempt, exc)
                except ValueError as exc:
                    logger.debug("WinGo history JSON decode error: url=%s attempt=%s error=%s", url, attempt, exc)

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

            if issue in (None, "") or number in (None, ""):
                continue

            try:
                number_int = int(str(number))
            except (TypeError, ValueError):
                continue

            if not 0 <= number_int <= 9:
                logger.debug("Skipping out-of-range WinGo number: period=%s number=%s", issue, number_int)
                continue

            result.append(
                {
                    "period": str(issue),
                    "number": number_int,
                    "color": str(color) if color is not None else "",
                }
            )

        return result


def create_sample_data(length: int = 120, seed: int = 42) -> List[int]:
    """Create deterministic pseudo-random draws for offline mode.

    The default seed preserves reproducible fallback behavior, while tests can
    override it when they need a different deterministic sequence.
    """
    rng = random.Random(seed)
    return [rng.randint(0, 9) for _ in range(max(10, length))]
