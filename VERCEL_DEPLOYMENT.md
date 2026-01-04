# Vercel Deployment Guide

## Quick Start

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

## Environment Variables

You need to set these environment variables in your Vercel project settings:

### Required

| Variable | Description | How to Get |
|----------|-------------|------------|
| `ANTHROPIC_API_KEY` | Claude API key for AI shark responses | [Anthropic Console](https://console.anthropic.com/) |

### Optional (for full features)

| Variable | Description | How to Get |
|----------|-------------|------------|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase Admin SDK credentials (JSON string) | Firebase Console > Project Settings > Service Accounts |
| `ELEVEN_LABS_API_KEY` | Text-to-speech for shark voices | [ElevenLabs](https://elevenlabs.io/) |

## Setting Environment Variables

### Via Vercel CLI

```bash
# Set each variable
vercel env add ANTHROPIC_API_KEY production
vercel env add FIREBASE_SERVICE_ACCOUNT_JSON production
vercel env add ELEVEN_LABS_API_KEY production
```

### Via Vercel Dashboard

1. Go to your project on [vercel.com](https://vercel.com)
2. Navigate to **Settings** > **Environment Variables**
3. Add each variable with the appropriate value

### Firebase Service Account Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to **Project Settings** > **Service Accounts**
4. Click **Generate New Private Key**
5. Copy the entire JSON contents
6. In Vercel, paste it as the value for `FIREBASE_SERVICE_ACCOUNT_JSON`

**Important:** The JSON must be a single line or properly escaped. You can minify it:

```bash
cat service_account.json | jq -c .
```

## API Routes

The deployment includes these serverless functions:

| Route | Function | Description |
|-------|----------|-------------|
| `POST /api/session/start` | `api/session.py` | Start a new pitch session |
| `POST /api/chat` | `api/chat.py` | Send message, get shark response |
| `GET /api/verify/defi/search?q=...` | `api/verify-defi.py` | Search DeFi protocols |
| `POST /api/verify/defi` | `api/verify-defi.py` | Verify DeFi protocol ownership |
| `POST /api/verify/trustmrr` | `api/verify-trustmrr.py` | Verify TrustMRR profile |
| `GET /api/leaderboard?type=verified` | `api/leaderboard.py` | Get leaderboard entries |

## Project Structure

```
shark-tank-simulator/
├── api/                    # Vercel serverless functions
│   ├── session.py         # Session management
│   ├── chat.py            # AI shark responses
│   ├── verify-defi.py     # DeFi verification
│   ├── verify-trustmrr.py # TrustMRR verification
│   ├── leaderboard.py     # Leaderboard API
│   └── requirements.txt   # Python dependencies
├── vercel.json            # Vercel configuration
├── index.html             # Main app
├── app.js                 # Frontend JavaScript
├── styles.css             # Styles
└── images/                # Static assets
```

## Local Development

The serverless functions are designed for Vercel, but you can run the Flask server locally:

```bash
cd server
pip install -r ../requirements.txt
python app.py
```

This starts the Flask server on `https://localhost:8443` with full SSE support.

## Troubleshooting

### "Anthropic API key not found"
- Ensure `ANTHROPIC_API_KEY` is set in Vercel environment variables
- Redeploy after adding the variable

### "Firebase not initialized"
- Check that `FIREBASE_SERVICE_ACCOUNT_JSON` contains valid JSON
- Make sure it's the complete service account key, not just the project ID

### CORS errors
- All API routes include CORS headers for `*` origin
- If issues persist, check the browser console for the exact error

### Cold start delays
- First request after inactivity may take 2-5 seconds
- This is normal for serverless functions

## Deployment Commands

```bash
# Deploy to production
vercel --prod

# Deploy preview (for testing)
vercel

# View deployment logs
vercel logs

# List environment variables
vercel env ls
```
