"""
Vercel Serverless Function: Leaderboard
Fetches leaderboard data from Firestore
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# Initialize Firebase
_firebase_app = None
_db = None


def initialize_firebase():
    """Initialize Firebase Admin SDK for Vercel."""
    global _firebase_app, _db

    if _firebase_app is not None:
        return _db

    if not HAS_FIREBASE:
        print("Firebase Admin SDK not installed")
        return None

    try:
        # Use service account JSON from environment variable
        cred_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')

        if cred_json:
            import json as json_lib
            cred_dict = json_lib.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            _db = firestore.client()
            return _db
        else:
            print("FIREBASE_SERVICE_ACCOUNT_JSON not set")
            return None

    except Exception as e:
        print(f"Firebase init error: {e}")
        return None


def get_leaderboard(verified_only=True, limit_count=50):
    """Fetch leaderboard entries from Firestore."""
    db = initialize_firebase()

    if not db:
        # Return mock data if Firebase not available
        return get_mock_leaderboard()

    try:
        # Query for successful deals
        pitches_ref = db.collection('pitches')
        query = pitches_ref.where('outcome.result', '==', 'deal')
        docs = query.stream()

        entries = []
        for doc in docs:
            data = doc.to_dict()
            verification = data.get('verification', {})

            # Filter by verification if needed
            if verified_only and verification.get('type') == 'unverified':
                continue

            entries.append(data)

        # Sort by deal amount descending
        entries.sort(key=lambda x: x.get('outcome', {}).get('dealAmount', 0) or 0, reverse=True)

        # Add rank and limit
        result = []
        for i, entry in enumerate(entries[:limit_count]):
            entry['rank'] = i + 1
            result.append(entry)

        return result

    except Exception as e:
        print(f"Firestore error: {e}")
        return get_mock_leaderboard()


def get_mock_leaderboard():
    """Return mock leaderboard data for development/fallback."""
    return [
        {
            'rank': 1,
            'userTwitterHandle': '@haydenzadams',
            'pitchData': {
                'companyName': 'Uniswap',
                'description': 'Decentralized exchange protocol'
            },
            'outcome': {
                'result': 'deal',
                'dealAmount': 2000000,
                'dealEquity': 5,
                'shark': 'Richard Hale'
            },
            'verification': {
                'type': 'verified',
                'level': 'verified',
                'protocol': {
                    'name': 'Uniswap',
                    'logo': 'https://icons.llama.fi/uniswap.png'
                },
                'metrics': {
                    'primaryLabel': '30d Fees',
                    'primaryValue': 43000000
                }
            }
        },
        {
            'rank': 2,
            'userTwitterHandle': '@staboratory',
            'pitchData': {
                'companyName': 'Aave',
                'description': 'Decentralized lending protocol'
            },
            'outcome': {
                'result': 'deal',
                'dealAmount': 1500000,
                'dealEquity': 8,
                'shark': 'Elena Brooks'
            },
            'verification': {
                'type': 'verified',
                'level': 'verified',
                'protocol': {
                    'name': 'Aave',
                    'logo': 'https://icons.llama.fi/aave.png'
                },
                'metrics': {
                    'primaryLabel': 'TVL',
                    'primaryValue': 12000000000
                }
            }
        }
    ]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Parse query params
        leaderboard_type = params.get('type', ['verified'])[0]
        limit = int(params.get('limit', ['50'])[0])

        verified_only = leaderboard_type == 'verified'
        entries = get_leaderboard(verified_only=verified_only, limit_count=limit)

        self._send_json({'entries': entries, 'type': leaderboard_type})

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
