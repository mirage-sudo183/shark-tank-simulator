# Shark Tank Simulator - Deployment Guide

This app uses a split architecture:
- **Frontend**: Deployed on Vercel (static files + simple API functions)
- **Backend**: Deployed on Railway (Flask with SSE support for real-time shark responses)

## Architecture Overview

```
┌─────────────────────┐         ┌─────────────────────┐
│      Vercel         │         │      Railway        │
│   (Frontend Host)   │         │   (Backend API)     │
│                     │         │                     │
│  - index.html       │  SSE    │  - Flask server     │
│  - app.js           │ ──────► │  - AI responses     │
│  - styles.css       │  REST   │  - TTS audio        │
│  - Firebase Auth    │         │  - Verification     │
└─────────────────────┘         └─────────────────────┘
```

## Prerequisites

- [Railway Account](https://railway.app/) (free tier available)
- [Vercel Account](https://vercel.com/) (free tier available)
- [Anthropic API Key](https://console.anthropic.com/)
- [Firebase Project](https://console.firebase.google.com/) (for auth)

---

## Step 1: Deploy Backend to Railway

### 1.1 Create Railway Project

1. Go to [railway.app](https://racilway.app/) and sign in
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `shark-tank-simulator` repository
4. Railway will auto-detect the Procfile and start building

### 1.2 Configure Environment Variables

In Railway dashboard, go to your service → **Variables** tab and add:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI responses |
| `ELEVEN_LABS_API_KEY` | No | ElevenLabs API for voice synthesis |
| `OPENAI_API_KEY` | No | OpenAI API for speech-to-text (Whisper) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | No | Firebase Admin SDK credentials (minified JSON) |

### 1.3 Get Your Railway URL

After deployment, Railway will assign a URL like:
```
https://shark-tank-simulator-production.up.railway.app
```

Copy this URL - you'll need it for the frontend configuration.

### 1.4 Verify Deployment

Test the health endpoint:
```bash
curl https://your-railway-url.up.railway.app/health
# Should return: {"service":"shark-tank-simulator","status":"healthy"}
```

---

## Step 2: Update Frontend Configuration

### 2.1 Set Railway Backend URL

Edit `app.js` and update the `RAILWAY_BACKEND_URL`:

```javascript
// Line ~20 in app.js
const RAILWAY_BACKEND_URL = 'https://YOUR-ACTUAL-RAILWAY-URL.up.railway.app';
```

### 2.2 Update Firebase Config (if using auth)

Ensure `firebase-config.js` has your Firebase project credentials.

---

## Step 3: Deploy Frontend to Vercel

### 3.1 Install Vercel CLI

```bash
npm i -g vercel
```

### 3.2 Deploy

```bash
# From project root
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name: shark-tank-simulator
# - Directory: ./
```

### 3.3 Set Environment Variables (Optional)

If using Vercel serverless functions as fallback:

```bash
vercel env add ANTHROPIC_API_KEY production
```

### 3.4 Deploy to Production

```bash
vercel --prod
```

---

## Step 4: Update CORS (if needed)

After deployment, update `server/app.py` CORS origins with your actual domains:

```python
CORS(app, origins=[
    "http://localhost:*",
    "https://localhost:*",
    "https://*.vercel.app",
    "https://shark-tank-simulator.vercel.app",
    "https://*.up.railway.app",
    "https://yourdomain.com",  # Add custom domain
], supports_credentials=True)
```

Redeploy Railway after CORS changes.

---

## Environment Variables Summary

### Railway Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Claude API for shark AI |
| `ELEVEN_LABS_API_KEY` | No | TTS voices |
| `OPENAI_API_KEY` | No | Speech-to-text |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | No | Auth + Firestore |
| `PORT` | Auto | Set by Railway automatically |

### Vercel Frontend (Optional fallback)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | No | For `/api/chat` fallback |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | No | For `/api/leaderboard` |

---

## Local Development

### Run Backend Locally

```bash
cd server
pip install -r ../requirements.txt
python app.py
# Runs on https://localhost:8443
```

### Run Frontend Locally

Just open `index.html` in a browser, or use a local server:

```bash
npx serve .
# Or
python -m http.server 8000
```

---

## Troubleshooting

### "SSE connection failed"

- Ensure Railway backend is running
- Check that `RAILWAY_BACKEND_URL` in `app.js` is correct
- Verify CORS allows your Vercel domain

### "CORS error"

- Add your Vercel URL to the CORS origins in `server/app.py`
- Redeploy Railway after changes

### "No audio from sharks"

- Check `ELEVEN_LABS_API_KEY` is set in Railway
- ElevenLabs free tier has usage limits

### "Authentication not working"

- Verify Firebase config in `firebase-config.js`
- Check Twitter/X OAuth settings in Firebase Console
- Ensure callback URL matches Vercel domain

### Railway Build Fails

Check the build logs. Common issues:
- Missing dependencies in `requirements.txt`
- Python version mismatch (uses `server/runtime.txt`)

---

## Project Files

### Railway (Backend)

```
Procfile                 # Start command for Railway
railway.json             # Railway configuration
server/
├── app.py               # Main Flask application
├── runtime.txt          # Python version
├── session.py           # Session management
├── sharks.py            # Shark personas
├── ai_client.py         # Claude API client
├── tts_client.py        # ElevenLabs TTS
├── rate_limiter.py      # Rate limiting
├── firebase_admin_init.py
└── verification/
    ├── defillama.py     # DeFi verification
    └── trustmrr.py      # MRR verification
```

### Vercel (Frontend)

```
vercel.json              # Vercel configuration
index.html               # Main HTML
app.js                   # Frontend JavaScript
styles.css               # Styles
firebase-config.js       # Firebase client config
api/                     # Serverless functions (fallback)
├── session.py
├── chat.py
├── leaderboard.py
├── verify-defi.py
├── verify-trustmrr.py
└── requirements.txt
```

---

## Custom Domain Setup

### Vercel

1. Go to Vercel Dashboard → Your Project → Settings → Domains
2. Add your domain
3. Update DNS records as instructed

### Railway

1. Go to Railway Dashboard → Your Service → Settings → Domains
2. Add custom domain
3. Update DNS records

After adding custom domains, update:
1. CORS origins in `server/app.py`
2. Firebase authorized domains
3. Twitter OAuth callback URLs
