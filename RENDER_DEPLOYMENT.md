# Render Cloud Deployment Guide (Free Tier)

This guide documents the exact steps to deploy the **BTC 15-Minute AI Trader & Confluence Engine** to Render Cloud for free, keep it running 24/7, and connect it to your mobile `.ipa`.

---

## 📁 Pre-configured Files Already in Codebase

1. **`requirements.txt`**: Specifies all required Python libraries (`fastapi`, `uvicorn`, `xgboost`, `scikit-learn`, `pandas`, `cryptography`, `yfinance`, etc.).
2. **`render.yaml`**: Pre-configures Render's build and startup commands automatically:
   ```yaml
   services:
     - type: web
       name: btc-ai-trader
       env: python
       plan: free
       buildCommand: pip install -r requirements.txt
       startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
       envVars:
         - key: PYTHON_VERSION
           value: 3.12.10
   ```

---

## 🚀 Step-by-Step Deployment Instructions

### Step 1: Push Local Code to GitHub
Ensure all recent changes are committed and pushed to your GitHub repository:
```powershell
git add .
git commit -m "Add Render deployment config and ML audit fixes"
git push origin main
```

---

### Step 2: Create Free Web Service on Render
1. Go to [dashboard.render.com](https://dashboard.render.com) and sign in (or create a free account—no credit card required).
2. Click **New +** (top right) and select **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your GitHub repo.
4. Render will read `render.yaml` and pre-fill the settings:
   * **Name**: `btc-ai-trader` (or any custom name)
   * **Region**: Oregon (US West) or Ohio (US East)
   * **Branch**: `main`
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Instance Type**: **Free** (\$0/mo)
5. Click **Deploy Web Service**. Render will install dependencies and start the app in ~2–3 minutes.
6. Once deployed, Render provides your live HTTPS URL:
   ```
   https://btc-ai-trader-xxxx.onrender.com
   ```

---

### Step 3: Keep it Awake 24/7 (Free Ping Trick)
Because Render's Free tier goes to sleep after 15 minutes of inactivity, set up a free automated ping:
1. Create a free account at [UptimeRobot.com](https://uptimerobot.com).
2. Click **Add New Monitor**:
   * **Monitor Type**: `HTTP(s)`
   * **Friendly Name**: `BTC AI Trader Keepalive`
   * **URL**: `https://<your-render-subdomain>.onrender.com/api/health`
   * **Monitoring Interval**: Every `5 minutes`
3. Click **Create Monitor**.
4. **Result:** UptimeRobot will ping your server every 5 minutes, preventing Render from ever falling asleep and allowing your background auto-trading loop to execute 24/7 for free.

---

### Step 4: Connecting Your Mobile `.ipa` to the Cloud Backend
When your backend is running in the cloud, update your mobile app configuration so it routes requests to your live Render URL instead of `localhost`:

1. In `capacitor.config.json` (or your frontend environment file):
   ```json
   {
     "server": {
       "url": "https://<your-render-subdomain>.onrender.com",
       "cleartext": false
     }
   }
   ```
2. Re-export your `.ipa` using `update_ipa.py`.
3. Now your iPhone app connects securely to your cloud backend from anywhere, even on cellular data!

---

## 🔒 Kalshi API Key Setup (Optional for Live Trading)
If you switch from Paper to Live trading on Render:
1. Open your Web Service in the Render Dashboard.
2. Navigate to **Environment**.
3. Add the following Environment Secrets:
   * `KALSHI_API_KEY_ID`: Your Kalshi Key ID
   * `KALSHI_PRIVATE_KEY`: Your RSA Private Key content (PEM)
4. Click **Save Changes**. Render will automatically restart with your encrypted credentials.
