# Railway Deployment Checklist

## ✅ Pre-Deployment Checklist

- [ ] Firebase credentials file exists: `bdg_predictor/firebase-adminsdk.json`
- [ ] `Procfile` exists in root directory
- [ ] `runtime.txt` exists with Python version
- [ ] `requirements.txt` has all dependencies
- [ ] `.gitignore` excludes `firebase-adminsdk.json` and `.env`
- [ ] Git repository initialized and pushed to GitHub

## 📋 Quick Steps

### 1️⃣ **Push to GitHub** (2 min)
```powershell
cd c:\Users\raval\OneDrive\Desktop\BDG
git init
git add .
git commit -m "BDG Collector ready for Railway"

# Create repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/BDG.git
git branch -M main
git push -u origin main
```

### 2️⃣ **Create Railway Project** (1 min)
1. Go to **https://railway.app**
2. Sign up with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your **BDG** repository
5. Hit **Deploy**

### 3️⃣ **Add Firebase Credentials** (3 min)
Railway detects your code and starts building. While it builds:

1. Open your Railway dashboard
2. Click your **"bdg-collector"** project
3. Go to **"Variables"** tab
4. Add environment variable:
   ```
   FIREBASE_SERVICE_ACCOUNT_PATH=/app/firebase-adminsdk.json
   ```

5. (Optional) Upload credentials file:
   - Click **"Upload File"** 
   - Select `bdg_predictor/firebase-adminsdk.json`
   - Set path to `/app/firebase-adminsdk.json`

### 4️⃣ **Check Logs** (1 min)
1. Go to **"Logs"** tab
2. Wait for deployment to finish
3. Look for:
   ```
   ✓ Firebase Admin SDK initialized successfully.
   ✓ MULTI-GAME COLLECTOR STARTED
   ✓ [WinGo_30S] Thread started
   ✓ [WinGo_1M] Thread started
   ✓ [WinGo_3M] Thread started
   ✓ [WinGo_5M] Thread started
   ```

### 5️⃣ **Verify Data Collection** (2 min)
1. Wait 60 seconds for collection to begin
2. Go to **Firestore Console**: https://console.firebase.google.com
3. Navigate to `bdg_history` collection
4. You should see new documents with real data!

---

## 🎯 Done!

Your collector now runs **24/7 on Railway** without your PC! 🎉

- Data accumulates in Firebase automatically
- Free tier gives you $5/month credit
- Cost: ~$0.10/month (basically free!)

---

## 📊 Later: Use Data for Model Training

Once you have 1000+ draws collected:

1. Download data from Firebase Firestore
2. Use Google Colab to train LSTM model
3. Save trained model to Google Drive
4. Website will use it for predictions

See `RAILWAY_DEPLOY.md` for troubleshooting.
