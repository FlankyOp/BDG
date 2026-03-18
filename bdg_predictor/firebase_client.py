import logging
import os
import time
from typing import Dict, Any, List, Optional, cast

import firebase_admin  # type: ignore[import]
from firebase_admin import credentials  # type: ignore[import]
from firebase_admin import db  # type: ignore[import]

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SERVICE_ACCOUNT_PATH = os.path.join(_HERE, "firebase-adminsdk.json")
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", DEFAULT_SERVICE_ACCOUNT_PATH)
DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://flankygod-bdg-default-rtdb.firebaseio.com")

PREDICTIONS_PATH = "/predictions/{game_code}"
GAME_STATE_PATH = "/game_state/{game_code}"
HIT_MISS_PATH = "/hit_miss/{game_code}"
RECENT_HISTORY_LIMIT = 10
HIT_MISS_HISTORY_LIMIT = 100
INIT_FAILURE_COOLDOWN_SECONDS = 60
MAX_CONSECUTIVE_INIT_FAILURES = 3

_firebase_initialized = False
_firebase_init_failures = 0
_last_init_failure_at = 0.0


def _is_valid_game_code(game_code: Any) -> bool:
    return isinstance(game_code, str) and bool(game_code.strip())


def _firebase_path(template: str, game_code: str) -> str:
    return template.format(game_code=game_code.strip())


def _should_skip_init_retry() -> bool:
    if _firebase_init_failures < MAX_CONSECUTIVE_INIT_FAILURES:
        return False
    return (time.time() - _last_init_failure_at) < INIT_FAILURE_COOLDOWN_SECONDS


def _trim_history(history_ref: Any, limit: int) -> None:
    try:
        snapshot = history_ref.get()  # type: ignore[attr-defined]
    except Exception as exc:
        logger.debug("Unable to inspect Firebase history for trimming: %s", exc)
        return

    if not isinstance(snapshot, dict):
        return

    snapshot_dict = cast(Dict[str, Any], snapshot)
    if len(snapshot_dict) <= limit:
        return

    items: List[tuple[str, Dict[str, Any]]] = [
        (str(key), cast(Dict[str, Any], value)) for key, value in snapshot_dict.items()
    ]
    items.sort(key=lambda item: str(item[1].get("evaluated_at", "")) or item[0])

    excess = len(items) - limit
    for key, _ in items[:excess]:
        try:
            history_ref.child(key).delete()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("Unable to trim Firebase history entry %s: %s", key, exc)


def get_latest_prediction(game_code: str) -> Optional[Dict[str, Any]]:
    """Return the latest prediction payload for a game code, if available."""
    if not _is_valid_game_code(game_code):
        logger.warning("Skipping Firebase read: invalid game code %r", game_code)
        return None
    if not init_firebase():
        return None

    try:
        ref: Any = db.reference(_firebase_path(PREDICTIONS_PATH, game_code))  # type: ignore[attr-defined]
        payload = ref.get()  # type: ignore[attr-defined]
        return cast(Optional[Dict[str, Any]], payload if isinstance(payload, dict) else None)
    except Exception as exc:
        logger.error("Error reading prediction from Firebase: %s", exc)
        return None


def init_firebase() -> bool:
    """Initialize the Firebase Admin SDK once, with retry throttling on failure."""
    global _firebase_initialized, _firebase_init_failures, _last_init_failure_at
    if _firebase_initialized:
        return True
    if _should_skip_init_retry():
        logger.debug("Skipping Firebase init retry during cooldown window")
        return False

    if SERVICE_ACCOUNT_PATH == DEFAULT_SERVICE_ACCOUNT_PATH:
        logger.warning("Using default Firebase service-account path: %s", SERVICE_ACCOUNT_PATH)
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        _firebase_init_failures += 1
        _last_init_failure_at = time.time()
        logger.warning("Firebase service-account file not found at %s", SERVICE_ACCOUNT_PATH)
        return False
        
    try:
        cred: Any = credentials.Certificate(SERVICE_ACCOUNT_PATH)  # type: ignore[attr-defined]
        initialize_app = getattr(firebase_admin, "initialize_app")
        initialize_app(cred, {
            'databaseURL': DATABASE_URL
        })
        _firebase_initialized = True
        _firebase_init_failures = 0
        _last_init_failure_at = 0.0
        logger.info("Firebase Admin SDK initialized successfully.")
        return True
    except Exception as e:
        _firebase_init_failures += 1
        _last_init_failure_at = time.time()
        logger.warning(f"Failed to initialize Firebase: {e}. Please ensure credentials are correct.")
        return False


def push_prediction(game_code: str, prediction_data: Dict[str, Any]) -> None:
    """Push the latest prediction payload to `/predictions/{game_code}`.

    Expected payload: the full predictor output dictionary containing primary,
    alternative, backup/strong possibility, summary, and metadata fields.
    """
    if not _is_valid_game_code(game_code):
        logger.warning("Skipping Firebase prediction push: invalid game code %r", game_code)
        return
    if not prediction_data:
        logger.warning("Skipping Firebase prediction push for %s: empty payload", game_code)
        return
    if not init_firebase():
        return
        
    try:
        ref: Any = db.reference(_firebase_path(PREDICTIONS_PATH, game_code))  # type: ignore[attr-defined]
        ref.set(prediction_data)  # type: ignore[attr-defined]
        logger.info(f"Successfully pushed prediction for {game_code} to Firebase.")
    except Exception as e:
        logger.error(f"Error pushing prediction to Firebase: {e}")


def push_game_state(game_code: str, live_data: Dict[str, Any], history_data: List[Dict[str, Any]]) -> None:
    """Push the current live game state to `/game_state/{game_code}`.

    `live_data` is expected to contain `current` and `next` blocks used by the UI.
    `history_data` should be a list of normalized draw rows, newest first.
    """
    if not _is_valid_game_code(game_code):
        logger.warning("Skipping Firebase game-state push: invalid game code %r", game_code)
        return
    if not live_data:
        logger.warning("Skipping Firebase game-state push for %s: empty live_data", game_code)
        return
    if not init_firebase():
        return
        
    try:
        state_payload: Dict[str, Any] = {
            "live": live_data,
            "recent_history": history_data[:RECENT_HISTORY_LIMIT] if history_data else []
        }
        ref: Any = db.reference(_firebase_path(GAME_STATE_PATH, game_code))  # type: ignore[attr-defined]
        ref.set(state_payload)  # type: ignore[attr-defined]
        logger.debug(f"Pushed game state for {game_code} to Firebase.")
    except Exception as e:
        logger.error(f"Error pushing game state to Firebase: {e}")


def push_hit_miss_status(game_code: str, status_data: Dict[str, Any]) -> None:
    """Store hit/miss evaluation and aggregate summary under `/hit_miss/{game_code}`.

    `status_data` is expected to contain `status`, `actual`, `predicted`, and
    `evaluated_at` fields produced by the controller.
    """
    if not _is_valid_game_code(game_code):
        logger.warning("Skipping Firebase hit/miss push: invalid game code %r", game_code)
        return
    status_block_raw = status_data.get("status", {})
    if not isinstance(status_block_raw, dict):
        logger.warning("Skipping Firebase hit/miss push for %s: invalid payload", game_code)
        return
    if not init_firebase():
        return

    try:
        base_ref: Any = db.reference(_firebase_path(HIT_MISS_PATH, game_code))  # type: ignore[attr-defined]
        latest_ref: Any = base_ref.child('latest')  # type: ignore[attr-defined]
        history_ref: Any = base_ref.child('history')  # type: ignore[attr-defined]
        summary_ref: Any = base_ref.child('summary')  # type: ignore[attr-defined]
        status_block = cast(Dict[str, Any], status_block_raw)

        latest_ref.set(status_data)  # type: ignore[attr-defined]
        history_ref.push(status_data)  # type: ignore[attr-defined]
        _trim_history(history_ref, HIT_MISS_HISTORY_LIMIT)

        def _update_summary(current: Any) -> Dict[str, Any]:
            current_dict = cast(Dict[str, Any], current) if isinstance(current, dict) else {}

            total = int(current_dict.get('total_predictions', 0)) + 1
            number_hit = int(current_dict.get('number_hit', 0)) + (1 if status_block.get('number') == 'HIT' else 0)
            number_miss = int(current_dict.get('number_miss', 0)) + (1 if status_block.get('number') == 'MISS' else 0)
            color_hit = int(current_dict.get('color_hit', 0)) + (1 if status_block.get('color') == 'HIT' else 0)
            color_miss = int(current_dict.get('color_miss', 0)) + (1 if status_block.get('color') == 'MISS' else 0)
            size_hit = int(current_dict.get('size_hit', 0)) + (1 if status_block.get('size') == 'HIT' else 0)
            size_miss = int(current_dict.get('size_miss', 0)) + (1 if status_block.get('size') == 'MISS' else 0)

            return {
                'total_predictions': total,
                'number_hit': number_hit,
                'number_miss': number_miss,
                'color_hit': color_hit,
                'color_miss': color_miss,
                'size_hit': size_hit,
                'size_miss': size_miss,
                'number_hit_rate': round((number_hit / total) * 100, 2),
                'color_hit_rate': round((color_hit / total) * 100, 2),
                'size_hit_rate': round((size_hit / total) * 100, 2),
                'updated_at': status_data.get('evaluated_at')
            }

        summary_ref.transaction(_update_summary)  # type: ignore[attr-defined]
        logger.info(f"Stored hit/miss status for {game_code} in Firebase.")
    except Exception as e:
        logger.error(f"Error pushing hit/miss status to Firebase: {e}")


# ============================================================
# Cloud Firestore — bdg_history collection
# ============================================================
# Your Firestore stores historical draw documents with fields:
#   number (int), color (str), size (str), period (str), ts (timestamp)
#
# These functions let us:
#   1. fetch_firestore_history()  → read all stored draws for LSTM training
#   2. push_draw_to_firestore()   → write each new draw result after every poll
# ============================================================

FIRESTORE_HISTORY_COLLECTION = "bdg_history"


def _get_firestore_client() -> Any:
    """Return an authenticated Cloud Firestore client, or None on failure."""
    if not init_firebase():
        return None
    try:
        from firebase_admin import firestore as _fs  # type: ignore[import]
        return _fs.client()
    except Exception as exc:
        logger.warning("Firestore client unavailable: %s", exc)
        return None


def fetch_firestore_history(limit: int = 5000) -> List[int]:
    """
    Read up to *limit* draw documents from the ``bdg_history`` Firestore collection,
    ordered oldest-first by the ``ts`` field.

    Returns a **newest-first** list of draw numbers (int 0–9) ready to feed
    directly into the LSTM / Markov trainer.

    Returns an empty list if Firestore is unreachable or the collection is empty.
    """
    client = _get_firestore_client()
    if client is None:
        return []

    try:
        col_ref: Any = client.collection(FIRESTORE_HISTORY_COLLECTION)
        docs = col_ref.order_by("ts").limit(limit).get()  # type: ignore[attr-defined]

        draws: List[int] = []
        for doc in docs:
            data: Dict[str, Any] = doc.to_dict() or {}
            raw_num = data.get("number")
            if raw_num is not None:
                try:
                    draws.append(int(raw_num))
                except (TypeError, ValueError):
                    continue

        logger.info(
            "[Firestore] Loaded %d historical draws from '%s'",
            len(draws),
            FIRESTORE_HISTORY_COLLECTION,
        )
        # Reverse so the list is newest-first (matches the rest of the codebase)
        return list(reversed(draws))

    except Exception as exc:
        logger.warning("[Firestore] Failed to read history: %s", exc)
        return []


def push_draw_to_firestore(period: str, number: int, color: str, size: str, game_code: Optional[str] = None) -> None:
    """
    Write a single completed draw result to the ``bdg_history`` Firestore collection.

    Document ID is the period string — duplicate writes are idempotent (set, not add).
    Optionally includes game_code to track which game mode (30S, 1M, 3M, 5M) the draw is from.
    """
    if not period:
        return

    client = _get_firestore_client()
    if client is None:
        return

    try:
        from firebase_admin import firestore as _fs  # type: ignore[import]
        doc_ref: Any = client.collection(FIRESTORE_HISTORY_COLLECTION).document(str(period))
        
        doc_data = {
            "period": str(period),
            "number": int(number),
            "color": str(color),
            "size": str(size),
            "ts": _fs.SERVER_TIMESTAMP,
        }
        
        # Add game_code if provided
        if game_code:
            doc_data["game_code"] = str(game_code)
        
        doc_ref.set(doc_data, merge=False)  # type: ignore[attr-defined]
        logger.debug("[Firestore] Stored draw period=%s number=%d game=%s", period, number, game_code or "default")
    except Exception as exc:
        logger.warning("[Firestore] Failed to push draw period=%s: %s", period, exc)
