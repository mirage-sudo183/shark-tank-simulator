"""
Vercel Serverless Function: Chat with Sharks
Handles pitch submission and user messages, returns shark responses directly
"""
import json
import os
import random
from http.server import BaseHTTPRequestHandler

# Import Anthropic
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Shark IDs (matches session.py and Flask server)
SHARK_IDS = ['marcus_kellan', 'victor_slate', 'elena_brooks', 'richard_hale', 'daniel_frost']

# Shark personas
SHARK_PERSONAS = {
    'marcus_kellan': {
        'name': 'Marcus Kellan',
        'style': 'Tech billionaire. Bold, direct, hates royalty deals. Asks about CAC, LTV, and scalability.',
        'catchphrase': "What's your customer acquisition cost?"
    },
    'victor_slate': {
        'name': 'Victor Slate',
        'style': 'Mr. Wonderful. Cold, calculating, loves royalty deals. All about the numbers and returns.',
        'catchphrase': "Here's the thing..."
    },
    'elena_brooks': {
        'name': 'Elena Brooks',
        'style': 'Queen of Retail. Warm, product-focused, wants to see demos and patents.',
        'catchphrase': "Is this patented?"
    },
    'richard_hale': {
        'name': 'Richard Hale',
        'style': 'Adventurous billionaire. Focuses on brand, experience, and customer journey.',
        'catchphrase': "What's the customer experience like?"
    },
    'daniel_frost': {
        'name': 'Daniel Frost',
        'style': 'Tech entrepreneur. Empathetic, encouraging, connects emotionally with founders.',
        'catchphrase': "Tell me your story."
    }
}


def generate_shark_response(shark_id, pitch_data, user_message=None, context=None):
    """Generate a shark response using Claude API."""

    if shark_id not in SHARK_PERSONAS:
        shark_id = 'marcus_kellan'  # Default fallback

    if not HAS_ANTHROPIC:
        return f"Interesting pitch! Tell me more about your business model."

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return f"{SHARK_PERSONAS[shark_id]['catchphrase']}"

    try:
        client = anthropic.Anthropic(api_key=api_key)

        persona = SHARK_PERSONAS[shark_id]

        system_prompt = f"""You are {persona['name']}, an investor on Shark Tank.
Personality: {persona['style']}

The entrepreneur is pitching: {pitch_data.get('companyName', 'their company')}
- Asking for: ${pitch_data.get('amountRaising', 'unknown'):,} for {pitch_data.get('equityPercent', 'unknown')}%
- Description: {pitch_data.get('companyDescription', 'No description')}
- Traction: {pitch_data.get('proofType', 'idea')} - {pitch_data.get('proofValue', 'N/A')}

Respond in character as this shark investor. Keep responses to 2-3 sentences.
Ask probing questions or make comments about the business.
If you want to make an offer, clearly state the amount and equity percentage."""

        user_prompt = user_message if user_message else "The entrepreneur just finished their pitch. Give your initial reaction and ask a question."

        if context:
            user_prompt = f"Previous conversation:\n{context}\n\nEntrepreneur says: {user_message}"

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return message.content[0].text

    except Exception as e:
        print(f"Claude API error: {e}")
        return f"{SHARK_PERSONAS[shark_id]['catchphrase']} Tell me more about your numbers."


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        action = data.get('action', 'message')
        pitch_data = data.get('pitchData', {})
        user_message = data.get('message', '')
        context = data.get('context', '')
        last_shark = data.get('lastShark', '')

        # Pick different shark than last one
        available = [s for s in SHARK_IDS if s != last_shark]
        shark_id = random.choice(available) if available else random.choice(SHARK_IDS)

        # Generate response
        response_text = generate_shark_response(shark_id, pitch_data, user_message, context)

        response = {
            'sharkId': shark_id,
            'sharkName': SHARK_PERSONAS[shark_id]['name'],
            'text': response_text,
            'offer': None  # TODO: parse offers from response
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
