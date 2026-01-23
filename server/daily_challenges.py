"""
Daily/Weekly Challenges for PitchTank (Phase 5)
Manages themed challenges with criteria for extra engagement.
"""

import time
from datetime import datetime, timedelta


# Challenge configurations by day of week
DAILY_CHALLENGES = {
    0: {  # Monday
        'id': 'monday_millions',
        'name': 'Million Dollar Monday',
        'description': 'Pitch a company valued at $1M+',
        'criteria': {'min_valuation': 1000000},
        'badge': '💰'
    },
    1: {  # Tuesday
        'id': 'tech_tuesday',
        'name': 'Tech Tuesday',
        'description': 'Pitch a tech/SaaS startup',
        'criteria': {'category_keywords': ['tech', 'saas', 'software', 'app', 'ai', 'platform']},
        'badge': '💻'
    },
    2: {  # Wednesday
        'id': 'wildcard_wednesday',
        'name': 'Wildcard Wednesday',
        'description': 'Get a deal with an unconventional structure (royalty, contingent, etc.)',
        'criteria': {'deal_type': 'unconventional'},
        'badge': '🃏'
    },
    3: {  # Thursday
        'id': 'shark_thursday',
        'name': 'Shark Survivor Thursday',
        'description': 'Get at least 3 sharks to make offers',
        'criteria': {'min_offers': 3},
        'badge': '🦈'
    },
    4: {  # Friday
        'id': 'funding_friday',
        'name': 'Funding Friday',
        'description': 'Raise the most funding today',
        'criteria': {'competition': 'highest_amount'},
        'badge': '🏆'
    },
    5: {  # Saturday
        'id': 'shark_showdown',
        'name': 'Shark Showdown Saturday',
        'description': 'Get a deal from a specific shark: Mr. Wonderful',
        'criteria': {'target_shark': 'victor'},
        'badge': '🎯'
    },
    6: {  # Sunday
        'id': 'super_sunday',
        'name': 'Super Sunday',
        'description': 'Beat your personal best deal amount',
        'criteria': {'beat_personal_best': True},
        'badge': '⭐'
    }
}

# Weekly challenge (rotates monthly)
WEEKLY_CHALLENGES = [
    {
        'id': 'pitch_perfect',
        'name': 'Pitch Perfect Week',
        'description': 'Complete 5 successful pitches this week',
        'criteria': {'min_deals': 5},
        'badge': '🎯',
        'reward': 'Pitch Perfect Badge'
    },
    {
        'id': 'shark_whisperer',
        'name': 'Shark Whisperer Week',
        'description': 'Get a deal from every shark type',
        'criteria': {'all_sharks': True},
        'badge': '🐋',
        'reward': 'Shark Whisperer Badge'
    },
    {
        'id': 'high_roller',
        'name': 'High Roller Week',
        'description': 'Accumulate $5M+ in total deals',
        'criteria': {'total_amount': 5000000},
        'badge': '🎰',
        'reward': 'High Roller Badge'
    },
    {
        'id': 'negotiator',
        'name': 'Master Negotiator Week',
        'description': 'Get better terms than asked 3 times',
        'criteria': {'better_terms_count': 3},
        'badge': '🤝',
        'reward': 'Negotiator Badge'
    }
]


def get_current_daily_challenge():
    """Get today's daily challenge."""
    day_of_week = datetime.utcnow().weekday()
    challenge = DAILY_CHALLENGES.get(day_of_week, DAILY_CHALLENGES[0])

    # Add time info
    now = datetime.utcnow()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    return {
        **challenge,
        'type': 'daily',
        'expires_at': int(end_of_day.timestamp() * 1000),
        'time_remaining_ms': int((end_of_day - now).total_seconds() * 1000)
    }


def get_current_weekly_challenge():
    """Get this week's weekly challenge."""
    # Calculate week of month (0-3)
    now = datetime.utcnow()
    week_of_month = (now.day - 1) // 7
    challenge = WEEKLY_CHALLENGES[week_of_month % len(WEEKLY_CHALLENGES)]

    # Calculate end of week (Sunday 23:59 UTC)
    days_until_sunday = 6 - now.weekday()
    end_of_week = now + timedelta(days=days_until_sunday)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=59, microsecond=0)

    return {
        **challenge,
        'type': 'weekly',
        'expires_at': int(end_of_week.timestamp() * 1000),
        'time_remaining_ms': int((end_of_week - now).total_seconds() * 1000)
    }


def check_challenge_completion(challenge, pitch_data, outcome, user_history=None):
    """
    Check if a pitch completes a challenge.

    Args:
        challenge: Challenge configuration
        pitch_data: The pitch data
        outcome: The pitch outcome
        user_history: Optional user pitch history for personal best checks

    Returns:
        dict: {completed: bool, reason: str}
    """
    criteria = challenge.get('criteria', {})

    # Check minimum valuation
    if 'min_valuation' in criteria:
        deal_amount = outcome.get('dealAmount', 0)
        deal_equity = outcome.get('dealEquity', 0)
        if deal_equity > 0:
            valuation = deal_amount / (deal_equity / 100)
            if valuation < criteria['min_valuation']:
                return {'completed': False, 'reason': f'Valuation too low (${valuation:,.0f})'}

    # Check category keywords
    if 'category_keywords' in criteria:
        description = (pitch_data.get('companyDescription', '') + ' ' +
                      pitch_data.get('companyName', '')).lower()
        if not any(kw in description for kw in criteria['category_keywords']):
            return {'completed': False, 'reason': 'Company category does not match'}

    # Check deal type
    if 'deal_type' in criteria and criteria['deal_type'] == 'unconventional':
        if not outcome.get('royalty') and not outcome.get('contingent'):
            return {'completed': False, 'reason': 'Need unconventional deal structure'}

    # Check minimum offers
    if 'min_offers' in criteria:
        offer_count = outcome.get('totalOffers', 1)
        if offer_count < criteria['min_offers']:
            return {'completed': False, 'reason': f'Only received {offer_count} offers'}

    # Check target shark
    if 'target_shark' in criteria:
        if outcome.get('sharkId') != criteria['target_shark']:
            return {'completed': False, 'reason': 'Need deal from specific shark'}

    # Check personal best
    if criteria.get('beat_personal_best') and user_history:
        best_amount = max((h.get('outcome', {}).get('dealAmount', 0) for h in user_history), default=0)
        if outcome.get('dealAmount', 0) <= best_amount:
            return {'completed': False, 'reason': 'Did not beat personal best'}

    return {'completed': True, 'reason': 'Challenge completed!'}


def get_challenge_leaderboard(challenge_id, limit_count=10):
    """
    Get leaderboard for a specific challenge.
    This would typically query Firestore for challenge participations.
    """
    # Placeholder - actual implementation would query Firestore
    return []
