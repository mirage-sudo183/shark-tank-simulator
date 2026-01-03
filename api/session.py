"""
Vercel Serverless Function: Session Management
Handles session creation and shark state initialization
"""
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler

# Shark configuration (matches Flask server and frontend)
SHARK_IDS = ['marcus_kellan', 'victor_slate', 'elena_brooks', 'richard_hale', 'daniel_frost']
SHARK_NAMES = {
    'marcus_kellan': 'Marcus Kellan',
    'victor_slate': 'Victor Slate',
    'elena_brooks': 'Elena Brooks',
    'richard_hale': 'Richard Hale',
    'daniel_frost': 'Daniel Frost'
}

# Initial confidence based on proof type
PROOF_CONFIDENCE = {
    'revenue': 70,
    'users': 60,
    'customers': 65,
    'idea': 40
}


def calculate_initial_confidence(shark_id, pitch_data):
    """Calculate initial shark confidence based on pitch data."""
    proof_type = pitch_data.get('proofType', 'idea')
    base_confidence = PROOF_CONFIDENCE.get(proof_type, 50)

    # Add some variation per shark
    shark_index = SHARK_IDS.index(shark_id) if shark_id in SHARK_IDS else 0
    variation = (shark_index - 2) * 5  # -10 to +10 based on shark

    return max(20, min(90, base_confidence + variation))


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        pitch_data = data.get('pitchData', {})
        verification = data.get('verification')
        session_id = str(uuid.uuid4())[:8]

        # Initialize shark states
        sharks = []
        for shark_id in SHARK_IDS:
            confidence = calculate_initial_confidence(shark_id, pitch_data)
            shark_state = {
                'id': shark_id,
                'name': SHARK_NAMES[shark_id],
                'status': 'live',
                'confidence': confidence,
                'isSpeaking': False,
                'hasOffered': False,
                'currentOffer': None
            }
            sharks.append(shark_state)

        response = {
            'sessionId': session_id,
            'sharks': sharks
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
