"""
TrustMRR Verification Module
Verifies SaaS MRR metrics via TrustMRR public profiles
"""

import requests
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup


TRUSTMRR_BASE_URL = "https://trustmrr.com"


def extract_mrr_from_profile(profile_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch and parse a TrustMRR public profile page.
    Extracts MRR value and Twitter handle for verification.

    Args:
        profile_url: Full URL or slug (e.g., 'trustmrr.com/startup/mycompany' or 'mycompany')

    Returns:
        Dict with MRR data and Twitter handle, or None if not found
    """
    # Normalize URL
    if not profile_url.startswith('http'):
        # Assume it's a slug
        slug = profile_url.replace('trustmrr.com/startup/', '').replace('trustmrr.com/', '').strip('/')
        profile_url = f"{TRUSTMRR_BASE_URL}/startup/{slug}"

    try:
        response = requests.get(profile_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; SharkTankSimulator/1.0)'
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract company name
        name_elem = soup.find('h1') or soup.find(class_='company-name')
        company_name = name_elem.get_text(strip=True) if name_elem else None

        # Extract MRR value - look for common patterns
        mrr_value = None
        mrr_text = None

        # Look for MRR in various formats
        mrr_patterns = [
            r'\$[\d,]+(?:\.\d{2})?\s*(?:MRR|/mo|per month)',
            r'MRR[:\s]*\$[\d,]+(?:\.\d{2})?',
            r'Monthly[:\s]*\$[\d,]+(?:\.\d{2})?'
        ]

        page_text = soup.get_text()
        for pattern in mrr_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                mrr_text = match.group()
                # Extract numeric value
                num_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', mrr_text)
                if num_match:
                    mrr_value = float(num_match.group(1).replace(',', ''))
                break

        # Look for Twitter handle
        twitter_handle = None
        twitter_link = soup.find('a', href=re.compile(r'twitter\.com/|x\.com/'))
        if twitter_link:
            href = twitter_link.get('href', '')
            handle_match = re.search(r'(?:twitter\.com|x\.com)/(@?\w+)', href)
            if handle_match:
                twitter_handle = handle_match.group(1).lstrip('@')

        # Also check for Twitter in text
        if not twitter_handle:
            twitter_match = re.search(r'@(\w{1,15})', page_text)
            if twitter_match:
                twitter_handle = twitter_match.group(1)

        # Extract verification badge/status
        is_verified = bool(soup.find(class_=re.compile(r'verified|badge|stripe')))

        if mrr_value is None and company_name is None:
            return None

        return {
            'source': 'trustmrr',
            'profile_url': profile_url,
            'company_name': company_name,
            'mrr': mrr_value,
            'mrr_display': mrr_text,
            'twitter_handle': twitter_handle,
            'stripe_verified': is_verified
        }

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        print(f"[TrustMRR] HTTP error: {e}")
        return None
    except Exception as e:
        print(f"[TrustMRR] Error fetching profile: {e}")
        return None


def verify_mrr_ownership(
    user_twitter_handle: str,
    profile_url: str
) -> Dict[str, Any]:
    """
    Verify if a user owns a TrustMRR profile by matching Twitter handles.

    Args:
        user_twitter_handle: The logged-in user's Twitter handle
        profile_url: TrustMRR profile URL or slug

    Returns:
        Verification result with MRR metrics
    """
    profile_data = extract_mrr_from_profile(profile_url)

    if not profile_data:
        return {
            'verified': False,
            'level': 'not_found',
            'message': 'TrustMRR profile not found or could not be parsed',
            'source': 'trustmrr'
        }

    # Normalize handles for comparison
    user_handle = user_twitter_handle.lower().lstrip('@')
    profile_twitter = (profile_data.get('twitter_handle') or '').lower().lstrip('@')

    # Check verification
    is_verified = False
    verification_level = 'claimed'
    message = 'MRR claimed but ownership not verified'

    if profile_twitter and user_handle == profile_twitter:
        is_verified = True
        verification_level = 'verified' if profile_data.get('stripe_verified') else 'twitter_match'
        message = f'Twitter @{user_handle} matches TrustMRR profile'
        if profile_data.get('stripe_verified'):
            message += ' (Stripe verified)'
    elif profile_twitter:
        message = f'Your Twitter @{user_handle} does not match profile Twitter @{profile_twitter}'
    else:
        message = 'Profile has no Twitter linked - ownership claimed'

    return {
        'verified': is_verified,
        'level': verification_level,
        'message': message,
        'source': 'trustmrr',
        'profile': {
            'url': profile_data.get('profile_url'),
            'company_name': profile_data.get('company_name'),
            'twitter': profile_data.get('twitter_handle')
        },
        'metrics': {
            'mrr': profile_data.get('mrr'),
            'mrr_display': profile_data.get('mrr_display'),
            'stripe_verified': profile_data.get('stripe_verified', False)
        }
    }


def format_mrr(mrr: float) -> str:
    """Format MRR for display."""
    if mrr >= 1_000_000:
        return f"${mrr / 1_000_000:.2f}M"
    elif mrr >= 1_000:
        return f"${mrr / 1_000:.1f}K"
    else:
        return f"${mrr:.0f}"
