"""
Session Management for Shark Tank Simulator
Handles pitch sessions, shark states, and offer tracking
"""

import uuid
import time
from threading import Lock


class SessionManager:
    """Manages pitch sessions and their state."""

    def __init__(self):
        self.sessions = {}
        self.lock = Lock()

    def create_session(self, pitch_data, user_id=None, twitter_handle=None):
        """Create a new pitch session."""
        session_id = str(uuid.uuid4())[:8]

        with self.lock:
            self.sessions[session_id] = {
                'id': session_id,
                'userId': user_id,  # Firebase user ID (if authenticated)
                'twitterHandle': twitter_handle,  # Twitter handle (if authenticated)
                'pitchData': pitch_data,
                'phase': 'pitch',  # pitch, qa, offers, closed
                'transcript': [],  # Pitch transcript
                'qaTranscript': [],  # Q&A conversation
                'sharks': {},  # Shark states by ID
                'offers': [],  # All offers made
                'counterOffers': [],  # User counter-offers
                'finalDeal': None,
                'createdAt': int(time.time() * 1000),
                'pitchDuration': 180,  # 3 minutes
                'pitchTimeUsed': 0
            }

        return session_id

    def get_session(self, session_id):
        """Get a session by ID."""
        with self.lock:
            return self.sessions.get(session_id)

    def update_session(self, session_id, updates):
        """Update session fields."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].update(updates)
                return True
        return False

    def set_phase(self, session_id, phase):
        """Set the current phase of the session."""
        return self.update_session(session_id, {'phase': phase})

    def set_transcript(self, session_id, transcript):
        """Set the pitch transcript."""
        return self.update_session(session_id, {'transcript': transcript})

    def add_qa_message(self, session_id, message):
        """Add a message to the Q&A transcript."""
        with self.lock:
            if session_id in self.sessions:
                message['timestamp'] = int(time.time() * 1000)
                self.sessions[session_id]['qaTranscript'].append(message)
                return True
        return False

    # =========================================================================
    # Shark State Management
    # =========================================================================

    def get_shark_state(self, session_id, shark_id):
        """Get the state of a specific shark."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return session['sharks'].get(shark_id, {})
        return {}

    def update_shark_state(self, session_id, shark_id, updates):
        """Update a shark's state."""
        with self.lock:
            if session_id in self.sessions:
                if shark_id not in self.sessions[session_id]['sharks']:
                    self.sessions[session_id]['sharks'][shark_id] = {}
                self.sessions[session_id]['sharks'][shark_id].update(updates)
                return True
        return False

    def get_all_shark_states(self, session_id):
        """Get all shark states for a session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return session['sharks']
        return {}

    # =========================================================================
    # Offer Management
    # =========================================================================

    def add_offer(self, session_id, offer):
        """Add a new offer to the session."""
        with self.lock:
            if session_id in self.sessions:
                offer['id'] = str(uuid.uuid4())[:8]
                offer['timestamp'] = int(time.time() * 1000)
                offer['status'] = 'pending'
                self.sessions[session_id]['offers'].append(offer)
                return offer['id']
        return None

    def get_offer(self, session_id, offer_id):
        """Get a specific offer by ID."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                for offer in session['offers']:
                    if offer.get('id') == offer_id:
                        return offer
        return None

    def get_pending_offers(self, session_id):
        """Get all pending offers."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return [o for o in session['offers'] if o.get('status') == 'pending']
        return []

    def update_offer_status(self, session_id, offer_id, status):
        """Update an offer's status."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                for offer in session['offers']:
                    if offer.get('id') == offer_id:
                        offer['status'] = status
                        return True
        return False

    def add_counter_offer(self, session_id, counter_offer):
        """Add a user counter-offer."""
        with self.lock:
            if session_id in self.sessions:
                counter_offer['id'] = str(uuid.uuid4())[:8]
                counter_offer['timestamp'] = int(time.time() * 1000)
                self.sessions[session_id]['counterOffers'].append(counter_offer)
                return counter_offer['id']
        return None

    def set_final_deal(self, session_id, deal):
        """Set the final accepted deal."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['finalDeal'] = deal
                self.sessions[session_id]['phase'] = 'closed'
                return True
        return False

    # =========================================================================
    # Cleanup
    # =========================================================================

    def delete_session(self, session_id):
        """Delete a session."""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
        return False

    def cleanup_old_sessions(self, max_age_hours=24):
        """Clean up sessions older than max_age_hours."""
        cutoff = int(time.time() * 1000) - (max_age_hours * 60 * 60 * 1000)
        with self.lock:
            to_delete = [
                sid for sid, session in self.sessions.items()
                if session.get('createdAt', 0) < cutoff
            ]
            for sid in to_delete:
                del self.sessions[sid]
            return len(to_delete)
