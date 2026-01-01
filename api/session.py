"""
Vercel Serverless Function: Session Management
"""
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler

# In-memory store (note: won't persist between function calls in production)
# For production, use Redis, Upstash, or Vercel KV
sessions = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        pitch_data = data.get('pitchData', {})
        session_id = str(uuid.uuid4())[:8]

        # Initialize session
        sessions[session_id] = {
            'pitchData': pitch_data,
            'transcript': [],
            'qaTranscript': [],
            'phase': 'pitch',
            'sharks': {}
        }

        # Initialize shark states
        shark_ids = ['marcus', 'victor', 'elena', 'richard', 'daniel']
        shark_names = {
            'marcus': 'Marcus Kellan',
            'victor': 'Victor Slate',
            'elena': 'Elena Brooks',
            'richard': 'Richard Hale',
            'daniel': 'Daniel Frost'
        }

        sharks = []
        for shark_id in shark_ids:
            shark_state = {
                'id': shark_id,
                'name': shark_names[shark_id],
                'status': 'live',
                'confidence': 50,
                'isSpeaking': False,
                'hasOffered': False,
                'currentOffer': None
            }
            sessions[session_id]['sharks'][shark_id] = shark_state
            sharks.append(shark_state)

        response = {
            'sessionId': session_id,
            'sharks': sharks
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
