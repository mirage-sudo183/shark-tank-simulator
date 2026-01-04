"""
Vercel Serverless Function: TrustMRR Verification
Verifies SaaS MRR claims via TrustMRR public profiles
"""
import json
import re
from http.server import BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup

TRUSTMRR_BASE_URL = "https://trustmrr.com"


def verify_mrr_ownership(profile_url, user_twitter_handle):
    """
    Verify MRR ownership via TrustMRR public profile.

    Args:
        profile_url: TrustMRR profile URL (e.g., trustmrr.com/startup/mycompany)
        user_twitter_handle: User's Twitter handle for verification

    Returns verification result with MRR data if available.
    """
    try:
        # Normalize URL
        if not profile_url.startswith('http'):
            profile_url = f"https://{profile_url}"

        # Validate it's a TrustMRR URL
        if 'trustmrr.com' not in profile_url.lower():
            return {
                'verified': False,
                'level': 'invalid',
                'message': 'URL must be a TrustMRR profile (trustmrr.com/startup/...)'
            }

        # Fetch the profile page
        response = requests.get(profile_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; SharkTankBot/1.0)'
        })

        if response.status_code == 404:
            return {
                'verified': False,
                'level': 'not_found',
                'message': 'TrustMRR profile not found'
            }

        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract company name
        company_name = None
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            company_name = title_tag.get_text().strip()

        # Look for MRR value
        mrr_value = None
        mrr_pattern = re.compile(r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:MRR|ARR|/mo))?', re.IGNORECASE)

        # Try to find MRR in common patterns
        for text in soup.stripped_strings:
            match = mrr_pattern.search(text)
            if match:
                mrr_str = match.group()
                # Parse the dollar amount
                amount_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', mrr_str)
                if amount_match:
                    mrr_value = float(amount_match.group(1).replace(',', ''))
                    break

        # Look for Twitter handle on the page
        profile_twitter = None
        twitter_links = soup.find_all('a', href=re.compile(r'twitter\.com|x\.com'))
        for link in twitter_links:
            href = link.get('href', '')
            twitter_match = re.search(r'(?:twitter\.com|x\.com)/(@?\w+)', href)
            if twitter_match:
                profile_twitter = twitter_match.group(1).lstrip('@').lower()
                break

        # Also check for @mentions in the page
        if not profile_twitter:
            for text in soup.stripped_strings:
                twitter_match = re.search(r'@(\w{4,15})', text)
                if twitter_match:
                    profile_twitter = twitter_match.group(1).lower()
                    break

        # Normalize user handle
        user_handle = user_twitter_handle.lower().lstrip('@') if user_twitter_handle else ''

        # Build response
        base_response = {
            'source': 'trustmrr',
            'profile': {
                'url': profile_url,
                'name': company_name,
                'twitter': profile_twitter
            },
            'metrics': {
                'mrr': mrr_value,
                'primaryMetric': 'mrr' if mrr_value else None,
                'primaryValue': mrr_value or 0,
                'primaryLabel': 'MRR' if mrr_value else 'No Data'
            }
        }

        # Check verification
        if profile_twitter and user_handle == profile_twitter:
            return {
                **base_response,
                'verified': True,
                'level': 'verified',
                'message': f'Verified! Twitter @{user_handle} matches TrustMRR profile'
            }

        if mrr_value:
            return {
                **base_response,
                'verified': False,
                'level': 'claimed',
                'message': 'MRR data found but Twitter verification failed'
            }

        return {
            **base_response,
            'verified': False,
            'level': 'no_metrics',
            'message': 'Could not extract MRR data from profile'
        }

    except requests.exceptions.RequestException as e:
        return {
            'verified': False,
            'level': 'error',
            'message': f'Failed to fetch TrustMRR profile: {str(e)}'
        }
    except Exception as e:
        return {
            'verified': False,
            'level': 'error',
            'message': f'Verification error: {str(e)}'
        }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        profile_url = data.get('profileUrl', '')
        user_twitter = data.get('userTwitter', '')

        if not profile_url:
            self._send_json({'error': 'Missing profileUrl'}, 400)
            return

        result = verify_mrr_ownership(profile_url, user_twitter)
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
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
