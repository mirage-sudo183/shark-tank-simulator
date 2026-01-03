"""
Rate Limiter for Shark Tank Simulator
Prevents abuse by limiting pitch frequency per user
"""

import time
from threading import Lock
from functools import wraps
from flask import request, jsonify


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self.requests = {}  # user_id -> list of timestamps
        self.lock = Lock()

        # Default limits
        self.daily_limit = 3
        self.weekly_limit = 10
        self.cooldown_seconds = 30

    def _cleanup_old_requests(self, user_id):
        """Remove requests older than 7 days."""
        if user_id not in self.requests:
            return

        now = time.time()
        week_ago = now - (7 * 24 * 60 * 60)
        self.requests[user_id] = [ts for ts in self.requests[user_id] if ts > week_ago]

    def check_rate_limit(self, user_id):
        """
        Check if user is within rate limits.

        Returns:
            tuple: (allowed: bool, error_message: str or None, remaining: dict)
        """
        if not user_id:
            # No rate limiting for anonymous users (they can't save to leaderboard anyway)
            return True, None, {'daily': self.daily_limit, 'weekly': self.weekly_limit}

        now = time.time()
        day_ago = now - (24 * 60 * 60)
        week_ago = now - (7 * 24 * 60 * 60)

        with self.lock:
            self._cleanup_old_requests(user_id)

            if user_id not in self.requests:
                self.requests[user_id] = []

            timestamps = self.requests[user_id]

            # Check cooldown (30 seconds between pitches)
            if timestamps and (now - timestamps[-1]) < self.cooldown_seconds:
                wait_time = int(self.cooldown_seconds - (now - timestamps[-1]))
                return False, f'Please wait {wait_time} seconds before your next pitch', {
                    'daily': self._count_since(timestamps, day_ago),
                    'weekly': self._count_since(timestamps, week_ago),
                    'cooldown': wait_time
                }

            # Check daily limit
            daily_count = self._count_since(timestamps, day_ago)
            if daily_count >= self.daily_limit:
                return False, f'Daily limit reached ({self.daily_limit} pitches/day). Try again tomorrow.', {
                    'daily': daily_count,
                    'weekly': self._count_since(timestamps, week_ago)
                }

            # Check weekly limit
            weekly_count = self._count_since(timestamps, week_ago)
            if weekly_count >= self.weekly_limit:
                return False, f'Weekly limit reached ({self.weekly_limit} pitches/week). Try again next week.', {
                    'daily': daily_count,
                    'weekly': weekly_count
                }

            return True, None, {
                'daily': self.daily_limit - daily_count - 1,
                'weekly': self.weekly_limit - weekly_count - 1
            }

    def record_request(self, user_id):
        """Record a new request for rate limiting."""
        if not user_id:
            return

        with self.lock:
            if user_id not in self.requests:
                self.requests[user_id] = []
            self.requests[user_id].append(time.time())

    def _count_since(self, timestamps, since):
        """Count timestamps since a given time."""
        return sum(1 for ts in timestamps if ts > since)

    def get_user_stats(self, user_id):
        """Get rate limit stats for a user."""
        if not user_id:
            return {
                'daily_remaining': self.daily_limit,
                'weekly_remaining': self.weekly_limit,
                'daily_limit': self.daily_limit,
                'weekly_limit': self.weekly_limit
            }

        now = time.time()
        day_ago = now - (24 * 60 * 60)
        week_ago = now - (7 * 24 * 60 * 60)

        with self.lock:
            self._cleanup_old_requests(user_id)
            timestamps = self.requests.get(user_id, [])
            daily_count = self._count_since(timestamps, day_ago)
            weekly_count = self._count_since(timestamps, week_ago)

            return {
                'daily_remaining': max(0, self.daily_limit - daily_count),
                'weekly_remaining': max(0, self.weekly_limit - weekly_count),
                'daily_limit': self.daily_limit,
                'weekly_limit': self.weekly_limit,
                'daily_used': daily_count,
                'weekly_used': weekly_count
            }


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(f):
    """
    Decorator to apply rate limiting to a route.
    Requires the route to have @optional_auth or @require_auth first.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = None
        if hasattr(request, 'user') and request.user:
            user_id = request.user.get('uid')

        allowed, error_message, remaining = rate_limiter.check_rate_limit(user_id)

        if not allowed:
            return jsonify({
                'error': error_message,
                'rate_limit': remaining
            }), 429

        # Record the request
        rate_limiter.record_request(user_id)

        return f(*args, **kwargs)

    return decorated_function
