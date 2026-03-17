# Implementation Plan

## Overview
Deploy the BDG Game Prediction Engine frontend (index.html + assets/) to Netlify for live hosting using Netlify CLI, enabling public access to the Firebase-connected dashboard while keeping Python backend local. This fits the hybrid architecture: frontend for real-time UI consuming Firebase data pushed by local Python server, providing instant global access without GitHub or complex setup.

The project uses Firebase Realtime Database for frontend-backend sync (predictions/game_state pushed from main.py/firebase_client.py). Frontend is pure static (HTML/JS/CSS, Firebase CDN SDK), confirmed self-contained from read files—no backend routes needed. Netlify handles static hosting perfectly, with Firebase config exposed in app.js (live: flankygod-bdg.firebaseapp.com).

No file rename needed (index.html exists). Deployment targets bdg_predictor/ contents. Post-deploy, run Python locally to populate Firebase for live predictions. No types/changes to code—pure infrastructure task.

## Types
No type system changes required—this is a deployment task with no code modifications.

## Files
No source files created, modified, or deleted. Deployment bundles existing static assets as-is.

- New files: None.
- Existing files to deploy (bundled): bdg_predictor/index.html, bdg_predictor/assets/css/styles.css, bdg_predictor/assets/js/app.js.
- Config updates: None.
- Build output: Netlify creates _site-like deploy dir automatically.

## Functions
No function modifications—deployment only.

## Classes
No class modifications—deployment only.

## Dependencies
Netlify CLI installation (system-wide).

- New: netlify-cli (via `npm install -g netlify-cli`—assumes Node.js 18+ installed on Windows 11).
- No project deps changed (frontend Firebase CDN; Python local).

## Testing
Verify static assets deploy correctly and Firebase connects.

- Pre-deploy: `netlify deploy --dry` (simulate).
- Post-deploy: Visit live URL, check browser console for Firebase init, toggle games, confirm live badge/status.
- Full test: Run `python bdg_predictor/main.py` locally (pushes to Firebase), refresh Netlify site, confirm predictions render.
- Run project 3x: Test WinGo_1M/3M/5M tabs, manual predict disabled (expected per app.js).

## Implementation Order
1. Install Netlify CLI globally (`npm install -g netlify-cli`).
2. Login to Netlify (`netlify login`).
3. CD to bdg_predictor/ and preview deploy (`cd bdg_predictor && netlify deploy --dir . --alias preview-$(date +%s)`).
4. Verify preview URL works (open in browser, check Firebase).
5. Production deploy (`netlify deploy --dir . --prod`).
6. Test live site with local Python running (populate Firebase).
7. Run site 3x: Switch games, confirm data sync.
8. Document live URL in README.md (optional append).

