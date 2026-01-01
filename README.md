# Shark Tank Simulator

An AI-powered Shark Tank experience where you pitch to 5 virtual investors who respond in real-time with their own voices.

## Features

- **3-minute pitch phase** - Speak your pitch, transcribed in real-time
- **15-minute total session** - Q&A with AI-powered sharks
- **5 unique shark personalities** - Each with distinct investment styles
- **Real-time voice responses** - Sharks speak using Eleven Labs TTS
- **Offers & negotiations** - Accept, counter, or decline deals
- **Dynamic endings** - Celebration music for deals, sad music if all sharks pass

## Required API Keys

Create a `.env` file in the `server/` directory with the following keys:

```env
# Required: Powers shark AI responses
ANTHROPIC_API_KEY=sk-ant-api03-...

# Required: Transcribes your speech to text
OPENAI_API_KEY=sk-proj-...

# Optional: Enables shark voice audio (text-only without this)
ELEVEN_LABS_API_KEY=sk_...
```

### Getting API Keys

| Service | Purpose | Get Key |
|---------|---------|---------|
| **Anthropic** | Shark AI responses (Claude) | [console.anthropic.com](https://console.anthropic.com/) |
| **OpenAI** | Speech-to-text (Whisper) | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Eleven Labs** | Text-to-speech voices | [elevenlabs.io](https://elevenlabs.io/) |

## Quick Start

1. **Install dependencies**
   ```bash
   cd server
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create SSL certificates** (required for microphone access)
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

3. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the server**
   ```bash
   cd server
   python app.py
   ```

5. **Open in browser**
   ```
   https://localhost:8443
   ```
   (Accept the self-signed certificate warning)

## Shark Personalities

| Name | Style | Specialty |
|------|-------|-----------|
| **Marcus Kellan** | Bold, direct | Tech investments, hates royalties |
| **Victor Slate** | Numbers-focused | Loves royalty deals |
| **Elena Brooks** | Product-focused | Retail and consumer products |
| **Richard Hale** | Brand-focused | Experience and storytelling |
| **Daniel Frost** | Encouraging | Tech startups, empathetic |

## Project Structure

```
├── index.html          # Main UI
├── styles.css          # Styling
├── app.js              # Frontend logic
├── server/
│   ├── app.py          # Flask backend
│   ├── ai_client.py    # Claude API integration
│   ├── sharks.py       # Shark personalities
│   ├── tts_client.py   # Eleven Labs integration
│   └── session.py      # Session management
└── images/sharks/      # Shark profile images
```

## How It Works

1. **Pitch Phase (3 min)**: Your speech is continuously transcribed via OpenAI Whisper
2. **Submit Pitch**: Full transcript is sent to all sharks as context
3. **Q&A Phase**: Sharks ask questions based on your pitch, powered by Claude
4. **Offers**: Sharks may make offers which you can accept, counter, or decline
5. **Outcome**: Get a deal (celebration) or all sharks pass (sad ending)

## License

MIT
