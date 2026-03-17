# Firebase Fix Plan

## Information Gathered
TODO.md shows type errors in firebase_client.py/main.py (Pylance). firebase_client.py already has `from typing import Dict, Any, List` and `push_game_state(game_code: str, live_data: Dict[str, Any], history_data: List[Dict[str, Any]])`—typing looks correct. main.py has `_get_recent_history(self, period: Optional[str]) -> List[Dict[str, Any]]` but called with `self._get_recent_history(period)` where period Optional[str]—potential None error. Firebase needs 'firebase-adminsdk.json' service account key file (missing?). Frontend Firebase config in app.js works (CDN compat). Python pushes to Firebase; local service account required.

No runtime errors visible; type fixes per TODO to resolve VSCode warnings.

## Plan
Fix Pylance type errors + add missing imports/methods per TODO.md Step 2-3.

bdg_predictor/firebase_client.py:
- No changes needed (already typed correctly).

bdg_predictor/main.py:
- Ensure `_get_recent_history` handles Optional[str] safely (already does).
- No call signature issue.

Add missing firebase-admin to requirements.txt.

Create firebase-adminsdk.json placeholder/note.

Test run `python bdg_predictor/main.py`.

## Dependent Files to be edited
- bdg_predictor/requirements.txt (add firebase-admin==6.5.0)
- bdg_predictor/firebase_client.py (remove #type: ignore if possible)
- bdg_predictor/main.py (fix call if needed)
- TODO.md (update progress)

## Followup steps
1. Install deps `pip install -r bdg_predictor/requirements.txt`
2. Create firebase-adminsdk.json from Firebase Console (Service Accounts)
3. Test `python bdg_predictor/main.py` 3x, check logs/Firestore
4. Deploy frontend to Netlify
5. Verify end-to-end sync

Confirm this plan and provide firebase-adminsdk.json or proceed?
