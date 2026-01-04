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


# Initialize on import if env vars are set
if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
    initialize_firebase()
