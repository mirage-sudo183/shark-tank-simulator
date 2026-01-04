"""
Twitter API v2 Integration for Shark Tank Simulator
Checks if a protocol's official Twitter account follows a user
"""

import os
import requests
from typing import Optional, Dict, Any


TWITTER_API_BASE = "https://api.twitter.com/2"


def get_bearer_token() -> Optional[str]:
    """Get Twitter API Bearer Token from environment."""
    return os.environ.get('TWITTER_BEARER_TOKEN')


def get_headers() -> Dict[str, str]:
    """Get authorization headers for Twitter API."""
    token = get_bearer_token()
    if not token:
        return {}
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_user_id_by_username(username: str) -> Optional[str]:
    """
    Get Twitter user ID from username.

    Args:
        username: Twitter handle without @ (e.g., "moremarketsxyz")

    Returns:
        User ID string or None if not found
    """
    token = get_bearer_token()
    if not token:
        print("[Twitter API] No bearer token configured")
        return None

    # Remove @ if present
    username = username.lstrip('@')

    url = f"{TWITTER_API_BASE}/users/by/username/{username}"

    try:
        response = requests.get(url, headers=get_headers(), timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('id')
        elif response.status_code == 404:
            print(f"[Twitter API] User @{username} not found")
            return None
        else:
            print(f"[Twitter API] Error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"[Twitter API] Error getting user ID: {e}")
        return None


def check_if_user_follows(
    source_username: str,
    target_username: str
) -> Dict[str, Any]:
    """
    Check if source_username follows target_username.

    This is used to verify if a protocol's official account follows a user,
    indicating the user is likely a team member or affiliate.

    Args:
        source_username: The account to check following list (e.g., protocol's Twitter)
        target_username: The account to look for in following list (e.g., user's Twitter)

    Returns:
        Dict with 'follows' boolean and 'error' if any
    """
    token = get_bearer_token()
    if not token:
        return {
            'follows': False,
            'error': 'Twitter API not configured',
            'checked': False
        }

    # Normalize usernames
    source_username = source_username.lstrip('@').lower()
    target_username = target_username.lstrip('@').lower()

    # Get user IDs
    source_id = get_user_id_by_username(source_username)
    if not source_id:
        return {
            'follows': False,
            'error': f'Could not find @{source_username}',
            'checked': False
        }

    target_id = get_user_id_by_username(target_username)
    if not target_id:
        return {
            'follows': False,
            'error': f'Could not find @{target_username}',
            'checked': False
        }

    # Check if source follows target
    # We need to paginate through following list
    url = f"{TWITTER_API_BASE}/users/{source_id}/following"
    params = {
        'max_results': 1000,  # Max allowed per request
        'user.fields': 'username'
    }

    try:
        # Twitter API has pagination, we'll check up to 3 pages (3000 accounts)
        pages_checked = 0
        max_pages = 3

        while pages_checked < max_pages:
            response = requests.get(url, headers=get_headers(), params=params, timeout=15)

            if response.status_code == 429:
                # Rate limited
                return {
                    'follows': False,
                    'error': 'Twitter API rate limit reached. Try again later.',
                    'checked': False
                }

            if response.status_code != 200:
                print(f"[Twitter API] Error {response.status_code}: {response.text}")
                return {
                    'follows': False,
                    'error': f'Twitter API error: {response.status_code}',
                    'checked': False
                }

            data = response.json()
            following_list = data.get('data', [])

            # Check if target is in this page of following
            for user in following_list:
                if user.get('id') == target_id or user.get('username', '').lower() == target_username:
                    return {
                        'follows': True,
                        'error': None,
                        'checked': True,
                        'source': source_username,
                        'target': target_username
                    }

            # Check for next page
            next_token = data.get('meta', {}).get('next_token')
            if not next_token:
                break

            params['pagination_token'] = next_token
            pages_checked += 1

        # Not found in following list
        return {
            'follows': False,
            'error': None,
            'checked': True,
            'source': source_username,
            'target': target_username
        }

    except Exception as e:
        print(f"[Twitter API] Error checking follows: {e}")
        return {
            'follows': False,
            'error': str(e),
            'checked': False
        }


def verify_team_membership(
    protocol_twitter: str,
    user_twitter: str
) -> Dict[str, Any]:
    """
    Verify if a user is likely a team member of a protocol.

    Checks if the protocol's official Twitter follows the user.

    Args:
        protocol_twitter: Protocol's official Twitter handle
        user_twitter: User's Twitter handle

    Returns:
        Verification result with level
    """
    result = check_if_user_follows(protocol_twitter, user_twitter)

    if result.get('follows'):
        return {
            'verified': True,
            'level': 'followed',
            'message': f'@{protocol_twitter} follows you - Team verified!',
            'details': result
        }
    elif result.get('checked'):
        return {
            'verified': False,
            'level': 'claimed',
            'message': f'@{protocol_twitter} does not follow @{user_twitter}. Marked as claimed.',
            'details': result
        }
    else:
        # API error or not configured - fall back to claimed
        return {
            'verified': False,
            'level': 'claimed',
            'message': result.get('error', 'Could not verify team membership'),
            'details': result
        }
