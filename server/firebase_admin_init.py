"""
Firebase Admin SDK initialization for Shark Tank Simulator.
Handles token verification and Firestore operations on the backend.
"""

import os
import json
from functools import wraps
from flask import request, jsonify

# Firebase Admin SDK imports
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Initialize Firebase Admin
_firebase_app = None
_db = None


def initialize_firebase():
    """
    Initialize Firebase Admin SDK.
    Uses GOOGLE_APPLICATION_CREDENTIALS env var or inline credentials.
    """
    global _firebase_app, _db

    if _firebase_app is not None:
        return _firebase_app, _db

    try:
        # Option 1: Use service account key file path
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

        # Option 2: Use inline JSON credentials (for Vercel/serverless)
        cred_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')

        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        elif cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        else:
            # Option 3: Use application default credentials (for GCP)
            cred = credentials.ApplicationDefault()

        _firebase_app = firebase_admin.initialize_app(cred, {
            'projectId': 'shark-tank-sim-app'
        })
        _db = firestore.client()
        print("Firebase Admin SDK initialized successfully")
        return _firebase_app, _db

    except Exception as e:
        print(f"Warning: Firebase Admin initialization failed: {e}")
        print("Authentication features will be disabled")
        return None, None


def get_firestore():
    """Get Firestore client instance."""
    global _db
    if _db is None:
        initialize_firebase()
    return _db


def verify_firebase_token(id_token):
    """
    Verify a Firebase ID token and return the decoded token.

    Args:
        id_token: The Firebase ID token string

    Returns:
        dict: Decoded token with user info (uid, email, etc.)

    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except auth.InvalidIdTokenError:
        raise ValueError("Invalid Firebase ID token")
    except auth.ExpiredIdTokenError:
        raise ValueError("Firebase ID token has expired")
    except Exception as e:
        raise ValueError(f"Token verification failed: {str(e)}")


def get_user_from_token(id_token):
    """
    Get user data from Firestore using the Firebase ID token.

    Args:
        id_token: The Firebase ID token string

    Returns:
        tuple: (uid, user_data) where user_data is the Firestore document
    """
    decoded = verify_firebase_token(id_token)
    uid = decoded['uid']

    db = get_firestore()
    if db is None:
        return uid, None

    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        return uid, user_doc.to_dict()
    else:
        return uid, None


def require_auth(f):
    """
    Decorator to require Firebase authentication on a Flask route.

    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            # request.user contains the decoded token
            # request.user_data contains Firestore user document
            return jsonify({'uid': request.user['uid']})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        id_token = auth_header.split('Bearer ')[1]

        try:
            decoded_token = verify_firebase_token(id_token)
            request.user = decoded_token

            # Optionally fetch user data from Firestore
            db = get_firestore()
            if db:
                user_ref = db.collection('users').document(decoded_token['uid'])
                user_doc = user_ref.get()
                request.user_data = user_doc.to_dict() if user_doc.exists else None
            else:
                request.user_data = None

            return f(*args, **kwargs)

        except ValueError as e:
            return jsonify({'error': str(e)}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401

    return decorated_function


def optional_auth(f):
    """
    Decorator that allows both authenticated and unauthenticated requests.
    If authenticated, request.user and request.user_data will be set.
    If not authenticated, they will be None.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            id_token = auth_header.split('Bearer ')[1]
            try:
                decoded_token = verify_firebase_token(id_token)
                request.user = decoded_token

                db = get_firestore()
                if db:
                    user_ref = db.collection('users').document(decoded_token['uid'])
                    user_doc = user_ref.get()
                    request.user_data = user_doc.to_dict() if user_doc.exists else None
                else:
                    request.user_data = None
            except Exception:
                request.user = None
                request.user_data = None
        else:
            request.user = None
            request.user_data = None

        return f(*args, **kwargs)

    return decorated_function


# ============ Firestore Operations ============

def save_pitch_to_firestore(user_id, pitch_data, outcome, verification=None):
    """
    Save a pitch result to Firestore.

    Args:
        user_id: Firebase user ID
        pitch_data: Dict with pitch details
        outcome: Dict with deal outcome
        verification: Optional dict with verification info

    Returns:
        str: The pitch document ID
    """
    db = get_firestore()
    if db is None:
        raise RuntimeError("Firestore not available")

    # Get user data for denormalization
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    pitch_ref = db.collection('pitches').document()
    pitch_ref.set({
        'id': pitch_ref.id,
        'userId': user_id,
        'userTwitterHandle': user_data.get('twitterHandle', 'unknown'),
        'userDisplayName': user_data.get('displayName', 'Anonymous'),
        'pitchData': pitch_data,
        'outcome': outcome,
        'verification': verification or {'type': 'unverified'},
        'createdAt': firestore.SERVER_TIMESTAMP
    })

    return pitch_ref.id


def get_leaderboard_from_firestore(verified_only=True, limit_count=50):
    """
    Get leaderboard entries from Firestore.

    Args:
        verified_only: If True, only return verified pitches
        limit_count: Maximum entries to return

    Returns:
        list: Leaderboard entries sorted by deal amount
    """
    db = get_firestore()
    if db is None:
        return []

    pitches_ref = db.collection('pitches')

    # Query for successful deals
    query = pitches_ref.where('outcome.result', '==', 'deal')

    if verified_only:
        query = query.where('verification.type', '!=', 'unverified')

    query = query.order_by('outcome.dealAmount', direction=firestore.Query.DESCENDING)
    query = query.limit(limit_count)

    docs = query.stream()
    entries = []
    for i, doc in enumerate(docs):
        data = doc.to_dict()
        entries.append({
            'rank': i + 1,
            **data
        })

    return entries


def get_user_pitches(user_id, limit_count=10):
    """Get a user's pitch history."""
    db = get_firestore()
    if db is None:
        return []

    query = db.collection('pitches') \
        .where('userId', '==', user_id) \
        .order_by('createdAt', direction=firestore.Query.DESCENDING) \
        .limit(limit_count)

    docs = query.stream()
    return [doc.to_dict() for doc in docs]


def update_user_verification(user_id, verification_type, verification_data):
    """
    Update user's verification status.

    Args:
        user_id: Firebase user ID
        verification_type: 'defi' or 'stripe' or 'trustmrr'
        verification_data: Dict with verification details
    """
    db = get_firestore()
    if db is None:
        raise RuntimeError("Firestore not available")

    user_ref = db.collection('users').document(user_id)
    user_ref.update({
        f'verifications.{verification_type}': verification_data
    })


# ============ Challenge Functions (Phase 3) ============

def save_challenge_to_firestore(challenge_data):
    """
    Save a new challenge to Firestore.

    Args:
        challenge_data: Dict with challenge details including:
            - creatorUserId: Firebase user ID
            - creatorTwitterHandle: Twitter handle
            - pitchData: The pitch data to replicate
            - creatorResult: The creator's outcome

    Returns:
        str: The challenge document ID
    """
    db = get_firestore()
    if db is None:
        raise RuntimeError("Firestore not available")

    import time
    challenge_ref = db.collection('challenges').document()

    challenge_doc = {
        'id': challenge_ref.id,
        'creatorUserId': challenge_data.get('creatorUserId'),
        'creatorTwitterHandle': challenge_data.get('creatorTwitterHandle', 'anonymous'),
        'pitchData': challenge_data.get('pitchData', {}),
        'creatorResult': challenge_data.get('creatorResult', {}),
        'attempts': [],
        'createdAt': firestore.SERVER_TIMESTAMP,
        'expiresAt': int(time.time() * 1000) + (7 * 24 * 60 * 60 * 1000)  # 7 days
    }

    challenge_ref.set(challenge_doc)
    return challenge_ref.id


def get_challenge_from_firestore(challenge_id):
    """
    Get a challenge by ID.

    Args:
        challenge_id: The challenge document ID

    Returns:
        dict: Challenge data or None if not found
    """
    db = get_firestore()
    if db is None:
        return None

    challenge_ref = db.collection('challenges').document(challenge_id)
    challenge_doc = challenge_ref.get()

    if challenge_doc.exists:
        return challenge_doc.to_dict()
    return None


def add_attempt_to_challenge(challenge_id, attempt_data):
    """
    Add an attempt to a challenge.

    Args:
        challenge_id: The challenge document ID
        attempt_data: Dict with attempt details including:
            - userId: Firebase user ID (optional)
            - twitterHandle: Twitter handle (optional)
            - result: The attempt's outcome

    Returns:
        bool: True if successful
    """
    db = get_firestore()
    if db is None:
        raise RuntimeError("Firestore not available")

    import time
    challenge_ref = db.collection('challenges').document(challenge_id)
    challenge_doc = challenge_ref.get()

    if not challenge_doc.exists:
        return False

    attempt = {
        'userId': attempt_data.get('userId'),
        'twitterHandle': attempt_data.get('twitterHandle', 'anonymous'),
        'result': attempt_data.get('result', {}),
        'completedAt': int(time.time() * 1000)
    }

    challenge_ref.update({
        'attempts': firestore.ArrayUnion([attempt])
    })
    return True


# ============ Weekly Leaderboard Functions (Phase 4) ============

def get_weekly_leaderboard(verified_only=True, limit_count=50):
    """
    Get leaderboard entries for the current week.

    Args:
        verified_only: If True, only return verified pitches
        limit_count: Maximum entries to return

    Returns:
        list: Leaderboard entries for this week, sorted by deal amount
    """
    db = get_firestore()
    if db is None:
        return []

    import time
    from datetime import datetime, timedelta

    # Calculate start of current week (Monday 00:00 UTC)
    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_ms = int(start_of_week.timestamp() * 1000)

    pitches_ref = db.collection('pitches')

    # Query for successful deals this week
    query = pitches_ref.where('outcome.result', '==', 'deal')

    # Note: Firestore requires composite index for multiple where clauses
    # For now, filter by week in application code
    query = query.order_by('outcome.dealAmount', direction=firestore.Query.DESCENDING)
    query = query.limit(limit_count * 2)  # Get extra to filter by week

    docs = query.stream()
    entries = []

    for doc in docs:
        data = doc.to_dict()
        created_at = data.get('createdAt')

        # Convert Firestore timestamp to milliseconds
        if hasattr(created_at, 'timestamp'):
            created_at_ms = int(created_at.timestamp() * 1000)
        elif isinstance(created_at, (int, float)):
            created_at_ms = int(created_at)
        else:
            continue

        # Filter by week
        if created_at_ms < week_start_ms:
            continue

        # Filter by verification if requested
        if verified_only:
            verification = data.get('verification', {})
            if verification.get('type') == 'unverified':
                continue

        entries.append(data)

        if len(entries) >= limit_count:
            break

    # Add ranks
    for i, entry in enumerate(entries):
        entry['rank'] = i + 1

    return entries


# Initialize on import if env vars are set
if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
    initialize_firebase()
