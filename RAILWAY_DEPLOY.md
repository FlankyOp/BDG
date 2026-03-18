# 🚀 Railway Deployment Guide

Deploy the BDG Multi-Game Collector to Railway.app for 24/7 automatic data collection.

## Step 1: Push Code to GitHub

```powershell
# Navigate to project directory
cd c:\Users\raval\OneDrive\Desktop\BDG

# Initialize git
git init
git add .
git commit -m "BDG Multi-Game Collector - ready for Railway"

# Create a GitHub repo at https://github.com/new
# Then push:
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/BDG.git
git branch -M main
git push -u origin main
```

## Step 2: Create Railway Account & Project

1. Go to **https://railway.app** (sign up with GitHub)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select your **BDG** repository

## Step 3: Add Environment Variables

Railway will automatically detect:
- `Procfile` → runs `python bdg_predictor/multi_game_collector.py`
- `runtime.txt` → uses Python 3.13
- `requirements.txt` → installs dependencies

But you need to add your Firebase credentials:

1. In Railway dashboard, go to your project
2. Click **"Variables"**
3. Add these environment variables:

```
FIREBASE_SERVICE_ACCOUNT_PATH=/app/firebase-adminsdk.json
```

## Step 4: Upload Firebase Credentials

Railway has a special process for this:

1. In **Variables**, scroll down to **"File Variables"**
2. Click **"Add File Variable"**
3. Set name: `FIREBASE_CREDS`
4. Copy the entire contents of `bdg_predictor/firebase-adminsdk.json`
5. Paste it as the file content
6. Save

Then add this to your code to load it:

```python
import os
import json

firebase_creds_path = os.getenv('FIREBASE_CREDS')
if firebase_creds_path:
    os.environ['FIREBASE_SERVICE_ACCOUNT_PATH'] = firebase_creds_path
```

**OR** (easier) - Use Railway's built-in secret management:

In **Variables** tab, paste your Firebase JSON directly:
```
FIREBASE_SERVICE_ACCOUNT_PATH=/app/firebase-adminsdk.json
```

And upload the file in **"File Variables"**.

## Step 5: Deploy

1. Click **"Deploy"** button
2. Railway will:
   - Install dependencies from `requirements.txt`
   - Run `python bdg_predictor/multi_game_collector.py`
   - Keep it running 24/7

3. View logs in the **"Logs"** tab to confirm it's working

## Step 6: Verify It's Running

Check the logs for:
```
✓ Firebase initialized successfully
✓ MULTI-GAME COLLECTOR STARTED
✓ [WinGo_30S] Thread started
✓ [WinGo_1M] Thread started
✓ [WinGo_3M] Thread started
✓ [WinGo_5M] Thread started
```

Then check Firebase Firestore → `bdg_history` collection to confirm new data is appearing.

## Troubleshooting

**Issue: Firebase credentials not found**
- Solution: Make sure you added the file variable correctly
- Check logs for the exact error

**Issue: Dependencies not installing**
- Go to **Settings** → **Build** → check that `requirements.txt` is being detected
- Manually add build command if needed

**Issue: Collector crashes after startup**
- Check **Logs** tab for error messages
- Common: API timeout → increase timeout in `config.py`
- Common: Firebase auth → verify credentials are correct

## Cost

**Railway Free Tier:**
- $5/month free credit
- Collector uses ~50-100MB RAM
- ~$0.10/month typical cost
- ✅ **Free for first month!**

---

**Need help?** Check Railway docs: https://docs.railway.app

**Once running:** Your collector will accumulate data indefinitely. Later, download this data to Google Colab for model training!
