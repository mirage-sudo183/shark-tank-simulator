"""
DefiLlama Verification Module
Verifies crypto/DeFi protocol metrics using DefiLlama's free API
"""

import requests
from typing import Optional, Dict, Any


DEFILLAMA_BASE_URL = "https://api.llama.fi"


def search_protocols(query: str) -> list:
    """
    Search for protocols by name.
    Returns list of matching protocols with basic info.
    """
    try:
        response = requests.get(f"{DEFILLAMA_BASE_URL}/protocols", timeout=10)
        response.raise_for_status()
        protocols = response.json()

        # Filter by query (case-insensitive)
        query_lower = query.lower()
        matches = []
        for protocol in protocols:
            name = protocol.get('name', '').lower()
            slug = protocol.get('slug', '').lower()
            if query_lower in name or query_lower in slug:
                matches.append({
                    'id': protocol.get('slug'),
                    'name': protocol.get('name'),
                    'tvl': protocol.get('tvl', 0),
                    'chain': protocol.get('chain'),
                    'category': protocol.get('category'),
                    'twitter': protocol.get('twitter'),
                    'logo': protocol.get('logo')
                })

        # Sort by TVL descending, limit to top 20
        matches.sort(key=lambda x: x.get('tvl', 0) or 0, reverse=True)
        return matches[:20]

    except Exception as e:
        print(f"[DefiLlama] Search error: {e}")
        return []


def get_protocol_details(protocol_slug: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific protocol.
    """
    try:
        response = requests.get(f"{DEFILLAMA_BASE_URL}/protocol/{protocol_slug}", timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract current TVL - the 'tvl' field is an array of historical values
        # Use currentChainTvls sum or last historical entry
        current_tvl = 0
        current_chain_tvls = data.get('currentChainTvls', {})
        if current_chain_tvls:
            current_tvl = sum(v for v in current_chain_tvls.values() if isinstance(v, (int, float)))
        elif isinstance(data.get('tvl'), list) and len(data.get('tvl', [])) > 0:
            # Fallback to last entry in historical TVL array
            last_entry = data['tvl'][-1]
            current_tvl = last_entry.get('totalLiquidityUSD', 0)

        return {
            'id': data.get('slug'),
            'name': data.get('name'),
            'tvl': current_tvl,
            'chainTvls': current_chain_tvls,
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


def get_protocol_fees(protocol_slug: str) -> Optional[Dict[str, Any]]:
    """
    Get fee/revenue data for a protocol from DefiLlama fees endpoint.
    """
    try:
        response = requests.get(f"https://api.llama.fi/summary/fees/{protocol_slug}", timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            'total24h': data.get('total24h'),
            'total7d': data.get('total7d'),
            'total30d': data.get('total30d'),
            'totalAllTime': data.get('totalAllTime'),
            'revenue24h': data.get('revenue24h'),
            'revenue7d': data.get('revenue7d'),
            'revenue30d': data.get('revenue30d')
        }

    except Exception as e:
        print(f"[DefiLlama] Fees error: {e}")
        return None


def verify_protocol_ownership(
    user_twitter_handle: str,
    protocol_slug: str,
    check_following: bool = True
) -> Dict[str, Any]:
    """
    Verify if a user owns/is affiliated with a protocol.

    Verification levels (in order of trust):
    - 'verified': User's Twitter matches protocol's official Twitter
    - 'followed': Protocol's official Twitter follows the user (team member)
    - 'claimed': User claims ownership but no verification found
    - 'no_metrics': Protocol exists but has no revenue/TVL data

    Args:
        user_twitter_handle: User's Twitter handle
        protocol_slug: DefiLlama protocol slug
        check_following: Whether to check if protocol follows user (requires Twitter API)

    Returns verification result with protocol metrics.
    """
    # Get protocol details
    protocol = get_protocol_details(protocol_slug)
    if not protocol:
        return {
            'verified': False,
            'level': 'not_found',
            'message': f'Protocol "{protocol_slug}" not found on DefiLlama'
        }

    # Get fee/revenue data
    fees = get_protocol_fees(protocol_slug)

    # Normalize Twitter handles for comparison
    user_handle = user_twitter_handle.lower().lstrip('@')
    protocol_twitter = (protocol.get('twitter') or '').lower().lstrip('@')

    # Build metrics - prioritize fees/revenue over TVL
    tvl = protocol.get('tvl', 0) or 0
    fees_30d = fees.get('total30d') if fees else None
    fees_7d = fees.get('total7d') if fees else None
    fees_24h = fees.get('total24h') if fees else None

    metrics = {
        'tvl': tvl,
        'mcap': protocol.get('mcap'),
        'fdv': protocol.get('fdv'),
        'fees30d': fees_30d,
        'fees7d': fees_7d,
        'fees24h': fees_24h
    }

    # Determine primary metric to display (revenue/fees first, then TVL)
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

    # Build base response
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

    # Check if protocol has any verifiable metrics (fees or TVL)
    has_metrics = (fees_30d and fees_30d > 0) or (fees_7d and fees_7d > 0) or (tvl > 0)

    if not has_metrics:
        return {
            **base_response,
            'verified': False,
            'level': 'no_metrics',
            'message': f'Protocol "{protocol.get("name")}" has no fees or TVL data on DefiLlama. Cannot verify claims.'
        }

    # Level 1: Check exact Twitter match
    if protocol_twitter and user_handle == protocol_twitter:
        return {
            **base_response,
            'verified': True,
            'level': 'verified',
            'message': f'Verified! Twitter @{user_handle} matches protocol official account'
        }

    # Level 2: Twitter following check - DISABLED for now (manual verification)
    # TODO: Re-enable when Twitter API rate limits are resolved
    # if protocol_twitter and check_following:
    #     from .twitter_api import verify_team_membership
    #     team_result = verify_team_membership(protocol_twitter, user_handle)
    #     if team_result.get('level') == 'followed':
    #         return {..., 'level': 'followed'}

    # Level 3: Claimed (allow submission, verify manually)
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


def format_tvl(tvl: float) -> str:
    """Format TVL for display."""
    if tvl >= 1_000_000_000:
        return f"${tvl / 1_000_000_000:.2f}B"
    elif tvl >= 1_000_000:
        return f"${tvl / 1_000_000:.2f}M"
    elif tvl >= 1_000:
        return f"${tvl / 1_000:.2f}K"
    else:
        return f"${tvl:.2f}"
