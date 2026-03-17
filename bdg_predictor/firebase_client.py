import firebase_admin  # type: ignore
from firebase_admin import credentials  # type: ignore
from firebase_admin import db  # type: ignore
import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# IMPORTANT: Provide a valid service account JSON and Realtime Database URL.
_HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", os.path.join(_HERE, "firebase-adminsdk.json"))
DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://flankygod-bdg-default-rtdb.firebaseio.com")

_firebase_initialized = False

def init_firebase():
    """Initializes the Firebase Admin SDK."""
    global _firebase_initialized
    if _firebase_initialized:
        return True
        
    try:
        cred: Any = credentials.Certificate(SERVICE_ACCOUNT_PATH)  # type: ignore
        firebase_admin.initialize_app(cred, {  # type: ignore
            'databaseURL': DATABASE_URL
        })
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize Firebase: {e}. Please ensure credentials are correct.")
        return False

def push_prediction(game_code: str, prediction_data: Dict[str, Any]):
    """Pushes a new prediction to Firebase Realtime Database."""
    if not init_firebase():
        return
        
    try:
        ref: Any = db.reference(f'/predictions/{game_code}')  # type: ignore
        ref.set(prediction_data)  # type: ignore
        logger.info(f"Successfully pushed prediction for {game_code} to Firebase.")
    except Exception as e:
        logger.error(f"Error pushing prediction to Firebase: {e}")

def push_game_state(game_code: str, live_data: Dict[str, Any], history_data: List[Dict[str, Any]]):
    """Pushes the current game state (countdown, last result) to Firebase."""
    if not init_firebase():
        return
        
    try:
        # We push live data and the most recent 10 history records for the UI
        state_payload: Dict[str, Any] = {
            "live": live_data,
            "recent_history": history_data[:10] if history_data else []
        }
        ref: Any = db.reference(f'/game_state/{game_code}')  # type: ignore
        ref.set(state_payload)  # type: ignore
        logger.debug(f"Pushed game state for {game_code} to Firebase.")
    except Exception as e:
        logger.error(f"Error pushing game state to Firebase: {e}")


def push_hit_miss_status(game_code: str, status_data: Dict[str, Any]) -> None:
    """Stores hit/miss evaluation and updates aggregate counters in Firebase."""
    if not init_firebase():
        return

    try:
        base_ref: Any = db.reference(f'/hit_miss/{game_code}')  # type: ignore
        latest_ref: Any = base_ref.child('latest')  # type: ignore
        history_ref: Any = base_ref.child('history')  # type: ignore
        summary_ref: Any = base_ref.child('summary')  # type: ignore

        latest_ref.set(status_data)  # type: ignore
        history_ref.push(status_data)  # type: ignore

        def _update_summary(current: Any) -> Dict[str, Any]:
            current_dict: Dict[str, Any] = current if isinstance(current, dict) else {}

            total = int(current_dict.get('total_predictions', 0)) + 1
            number_hit = int(current_dict.get('number_hit', 0)) + (1 if status_data['status']['number'] == 'HIT' else 0)
            number_miss = int(current_dict.get('number_miss', 0)) + (1 if status_data['status']['number'] == 'MISS' else 0)
            color_hit = int(current_dict.get('color_hit', 0)) + (1 if status_data['status']['color'] == 'HIT' else 0)
            color_miss = int(current_dict.get('color_miss', 0)) + (1 if status_data['status']['color'] == 'MISS' else 0)
            size_hit = int(current_dict.get('size_hit', 0)) + (1 if status_data['status']['size'] == 'HIT' else 0)
            size_miss = int(current_dict.get('size_miss', 0)) + (1 if status_data['status']['size'] == 'MISS' else 0)

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

        summary_ref.transaction(_update_summary)  # type: ignore
        logger.info(f"Stored hit/miss status for {game_code} in Firebase.")
    except Exception as e:
        logger.error(f"Error pushing hit/miss status to Firebase: {e}")
