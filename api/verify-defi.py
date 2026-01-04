"""
Vercel Serverless Function: DeFi Verification via DefiLlama
Handles protocol search and ownership verification
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

DEFILLAMA_BASE_URL = "https://api.llama.fi"
DEFILLAMA_COINS_URL = "https://coins.llama.fi"
FEES_API_URL = "https://fees.llama.fi"


def search_protocols(query):
    """Search for protocols on DefiLlama."""
    try:
        response = requests.get(f"{DEFILLAMA_BASE_URL}/protocols", timeout=10)
        response.raise_for_status()
        all_protocols = response.json()

        query_lower = query.lower()
        matches = []

        for protocol in all_protocols:
            name = protocol.get('name', '').lower()
            slug = protocol.get('slug', '').lower()

            if query_lower in name or query_lower in slug:
                matches.append({
                    'id': protocol.get('slug'),
                    'name': protocol.get('name'),
                    'tvl': protocol.get('tvl', 0),
                    'logo': protocol.get('logo'),
                    'category': protocol.get('category'),
                    'chains': protocol.get('chains', [])[:5]
                })

        # Sort by TVL descending, limit to 10 results
        matches.sort(key=lambda x: x.get('tvl', 0) or 0, reverse=True)
        return matches[:10]

    except Exception as e:
        print(f"[DefiLlama] Search error: {e}")
        return []


def get_protocol_details(protocol_slug):
    """Get detailed information about a specific protocol."""
    try:
        response = requests.get(f"{DEFILLAMA_BASE_URL}/protocol/{protocol_slug}", timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract current TVL
        current_tvl = 0
        current_chain_tvls = data.get('currentChainTvls', {})
        if current_chain_tvls:
            current_tvl = sum(v for v in current_chain_tvls.values() if isinstance(v, (int, float)))
        elif isinstance(data.get('tvl'), list) and len(data.get('tvl', [])) > 0:
            last_entry = data['tvl'][-1]
            current_tvl = last_entry.get('totalLiquidityUSD', 0)

        return {
            'id': data.get('slug'),
            'name': data.get('name'),
            'tvl': current_tvl,
            'twitter': data.get('twitter'),
            'url': data.get('url'),
            'description': data.get('description'),
            'category': data.get('category'),
            'chains': data.get('chains', []),
            'logo': data.get('logo'),
            'mcap': data.get('mcap'),
            'fdv': data.get('fdv')
        }

    except Exception as e:
        print(f"[DefiLlama] Protocol details error: {e}")
        return None


def get_protocol_fees(protocol_slug):
    """Get fee/revenue data for a protocol."""
    try:
        response = requests.get(f"{FEES_API_URL}/summary/fees/{protocol_slug}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'total24h': data.get('total24h'),
                'total7d': data.get('total7d'),
                'total30d': data.get('total30d')
            }
        return None
    except Exception as e:
        print(f"[DefiLlama] Fees error: {e}")
        return None


def verify_protocol_ownership(user_twitter_handle, protocol_slug):
    """Verify if a user owns/is affiliated with a protocol."""
    protocol = get_protocol_details(protocol_slug)
    if not protocol:
        return {
            'verified': False,
            'level': 'not_found',
            'message': f'Protocol "{protocol_slug}" not found on DefiLlama'
        }

    fees = get_protocol_fees(protocol_slug)

    # Normalize Twitter handles
    user_handle = user_twitter_handle.lower().lstrip('@')
    protocol_twitter = (protocol.get('twitter') or '').lower().lstrip('@')

    # Build metrics
    tvl = protocol.get('tvl', 0) or 0
    fees_30d = fees.get('total30d') if fees else None
    fees_7d = fees.get('total7d') if fees else None

    metrics = {
        'tvl': tvl,
        'mcap': protocol.get('mcap'),
        'fdv': protocol.get('fdv'),
        'fees30d': fees_30d,
        'fees7d': fees_7d
    }

    # Determine primary metric
    if fees_30d and fees_30d > 0:
        metrics['primaryMetric'] = 'fees30d'
        metrics['primaryValue'] = fees_30d
        metrics['primaryLabel'] = '30d Fees'
    elif fees_7d and fees_7d > 0:
        metrics['primaryMetric'] = 'fees7d'
        metrics['primaryValue'] = fees_7d
        metrics['primaryLabel'] = '7d Fees'
    elif tvl > 0:
        metrics['primaryMetric'] = 'tvl'
        metrics['primaryValue'] = tvl
        metrics['primaryLabel'] = 'TVL'
    else:
        metrics['primaryMetric'] = None
        metrics['primaryValue'] = 0
        metrics['primaryLabel'] = 'No Data'

    base_response = {
        'source': 'defillama',
        'protocol': {
            'id': protocol.get('id'),
            'name': protocol.get('name'),
            'twitter': protocol.get('twitter'),
            'category': protocol.get('category'),
            'url': protocol.get('url'),
            'logo': protocol.get('logo')
        },
        'metrics': metrics
    }

    # Check if protocol has verifiable metrics
    has_metrics = (fees_30d and fees_30d > 0) or (fees_7d and fees_7d > 0) or (tvl > 0)

    if not has_metrics:
        return {
            **base_response,
            'verified': False,
            'level': 'no_metrics',
            'message': f'Protocol "{protocol.get("name")}" has no fees or TVL data'
        }

    # Check exact Twitter match
    if protocol_twitter and user_handle == protocol_twitter:
        return {
            **base_response,
            'verified': True,
            'level': 'verified',
            'message': f'Verified! Twitter @{user_handle} matches protocol official account'
        }

    # Claimed (no verification)
    if protocol_twitter:
        message = f'Claimed: @{user_handle} not verified as @{protocol_twitter} team member'
    else:
        message = 'Claimed: Protocol has no Twitter on DefiLlama'

    return {
        **base_response,
        'verified': False,
        'level': 'claimed',
        'message': message
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle protocol search requests."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query = params.get('q', [''])[0]

        if not query or len(query) < 2:
            self._send_json({'results': [], 'error': 'Query too short'})
            return

        results = search_protocols(query)
        self._send_json({'results': results})

    def do_POST(self):
        """Handle verification requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        protocol_slug = data.get('protocolId') or data.get('protocolSlug')
        user_twitter = data.get('userTwitter', '')

        if not protocol_slug:
            self._send_json({'error': 'Missing protocolId'}, 400)
            return

        result = verify_protocol_ownership(user_twitter, protocol_slug)
        self._send_json(result)

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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
