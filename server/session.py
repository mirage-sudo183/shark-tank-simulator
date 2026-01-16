"""
Session Management for Shark Tank Simulator
Handles pitch sessions, shark states, and offer tracking
"""

import uuid
import time
from threading import Lock

# Import belief state class
from sharks import InvestorBeliefState, SHARK_IDS
from deal_flow import DealMode, OfferLifecycle, DealResolution


class SessionManager:
    """Manages pitch sessions and their state."""

    def __init__(self):
        self.sessions = {}
        self.lock = Lock()

    def create_session(self, pitch_data, user_id=None, twitter_handle=None):
        """Create a new pitch session."""
        session_id = str(uuid.uuid4())[:8]

        # Initialize deal mode and offer lifecycle managers
        deal_mode = DealMode()
        offer_lifecycle = OfferLifecycle()

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
                'pitchDuration': 60,  # 1 minute
                'pitchTimeUsed': 0,
                # New deal flow state
                'deal_mode': deal_mode.to_dict(),
                'offer_lifecycle': offer_lifecycle.to_dict(),
                'deal_resolution': None  # Set when deal is accepted
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

    def initialize_shark_states(self, session_id, pitch_data):
        """Initialize all shark states with belief states for a session."""
        with self.lock:
            if session_id not in self.sessions:
                return False

            for shark_id in SHARK_IDS:
                belief_state = InvestorBeliefState(shark_id, pitch_data)
                self.sessions[session_id]['sharks'][shark_id] = {
                    'status': 'live',  # 'live' or 'out'
                    'confidence': 50,  # 0-100
                    'belief_state': belief_state.to_dict(),
                    'dialogue_history': [],  # Track what they've said
                    'offers_made': [],  # Track offers from this shark
                    'last_action_type': None,  # ASK, EXPRESS, OFFER, REJECT, etc.
                    'question_count': 0,
                    # Confidence flag system
                    'flagged_for_offer': False,  # True when confidence >= 70
                    'flagged_for_out': False,  # True when confidence < 25
                    'has_made_offer': False,  # Track if shark has made any offer
                    'post_offer_sensitivity': 1.0,  # Multiplier for confidence changes (0.5 after offer)
                    'went_out_at': None  # Timestamp when went out (for return logic)
                }
            return True

    def get_shark_belief_state(self, session_id, shark_id):
        """Get the belief state for a specific shark."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session and shark_id in session['sharks']:
                state_dict = session['sharks'][shark_id].get('belief_state', {})
                return InvestorBeliefState.from_dict(state_dict)
        return None

    def update_shark_belief_state(self, session_id, shark_id, belief_state):
        """Update a shark's belief state."""
        with self.lock:
            if session_id in self.sessions:
                if shark_id in self.sessions[session_id]['sharks']:
                    state_dict = belief_state.to_dict() if hasattr(belief_state, 'to_dict') else belief_state
                    self.sessions[session_id]['sharks'][shark_id]['belief_state'] = state_dict
                    return True
        return False

    def add_shark_dialogue(self, session_id, shark_id, dialogue_entry):
        """
        Add a dialogue entry to a shark's history.
        dialogue_entry should include: type, content, and optional metadata
        """
        with self.lock:
            if session_id in self.sessions:
                if shark_id in self.sessions[session_id]['sharks']:
                    dialogue_entry['timestamp'] = int(time.time() * 1000)
                    self.sessions[session_id]['sharks'][shark_id]['dialogue_history'].append(dialogue_entry)
                    return True
        return False

    def get_shark_dialogue_history(self, session_id, shark_id):
        """Get the dialogue history for a specific shark."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session and shark_id in session['sharks']:
                return session['sharks'][shark_id].get('dialogue_history', [])
        return []

    def record_shark_action(self, session_id, shark_id, action_type):
        """Record the last action type for a shark."""
        with self.lock:
            if session_id in self.sessions and shark_id in self.sessions[session_id]['sharks']:
                self.sessions[session_id]['sharks'][shark_id]['last_action_type'] = action_type
                if action_type == 'ASK':
                    self.sessions[session_id]['sharks'][shark_id]['question_count'] = \
                        self.sessions[session_id]['sharks'][shark_id].get('question_count', 0) + 1
                return True
        return False

    def record_shark_offer(self, session_id, shark_id, offer):
        """Record an offer made by a shark."""
        with self.lock:
            if session_id in self.sessions and shark_id in self.sessions[session_id]['sharks']:
                self.sessions[session_id]['sharks'][shark_id]['offers_made'].append({
                    'offer_id': offer.get('id'),
                    'deal_type': offer.get('deal_type', 'cash_equity'),
                    'timestamp': int(time.time() * 1000)
                })
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
    # Deal Mode Management
    # =========================================================================

    def get_deal_mode(self, session_id):
        """Get the DealMode object for a session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session and session.get('deal_mode'):
                return DealMode.from_dict(session['deal_mode'])
        return None

    def update_deal_mode(self, session_id, deal_mode):
        """Update the deal mode state."""
        with self.lock:
            if session_id in self.sessions:
                state_dict = deal_mode.to_dict() if hasattr(deal_mode, 'to_dict') else deal_mode
                self.sessions[session_id]['deal_mode'] = state_dict
                return True
        return False

    def add_offer_to_deal_mode(self, session_id, offer):
        """
        Add an offer to the deal mode and handle mode transitions.
        Returns the mode change result.
        """
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return None

        result = deal_mode.add_offer(offer)
        self.update_deal_mode(session_id, deal_mode)
        return result

    def get_competing_offers(self, session_id, exclude_shark_id=None):
        """Get all competing offers, optionally excluding a specific shark."""
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return []
        return deal_mode.get_competing_offers(exclude_shark_id)

    def initiate_final_offer(self, session_id, offer_id):
        """
        Initiate final offer mode with countdown timer.
        Returns the mode change result with countdown info.
        """
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return {'error': 'No deal mode found'}

        result = deal_mode.initiate_final_offer(offer_id)
        self.update_deal_mode(session_id, deal_mode)
        return result

    def check_final_offer_expired(self, session_id):
        """Check if a final offer has expired."""
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return False

        if deal_mode.current_mode == 'final_offer' and deal_mode.final_offer_expires_at:
            if time.time() > deal_mode.final_offer_expires_at:
                # Mark offer as expired
                for offer in deal_mode.pending_offers:
                    if offer.get('id') == deal_mode.final_offer_id:
                        offer['status'] = 'expired'
                deal_mode.current_mode = 'closed'
                self.update_deal_mode(session_id, deal_mode)
                return True
        return False

    def get_deal_mode_status(self, session_id):
        """Get the current deal mode status with all relevant info."""
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return None

        status = {
            'mode': deal_mode.current_mode,
            'active_offers_count': len(deal_mode.pending_offers),
            'active_offers': deal_mode.pending_offers,
            'best_offer': deal_mode.get_best_competing_offer(),  # Get best from pending
            'is_bidding_war': deal_mode.current_mode == 'bidding_war'
        }

        if deal_mode.current_mode == 'final_offer':
            status['final_offer_id'] = deal_mode.final_offer_id
            status['final_offer_expires_at'] = deal_mode.final_offer_expires_at
            if deal_mode.final_offer_expires_at:
                status['seconds_remaining'] = max(0, deal_mode.final_offer_expires_at - time.time())

        return status

    # =========================================================================
    # Offer Lifecycle Management
    # =========================================================================

    def get_offer_lifecycle(self, session_id):
        """Get the OfferLifecycle object for a session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session and session.get('offer_lifecycle'):
                return OfferLifecycle.from_dict(session['offer_lifecycle'])
        return None

    def update_offer_lifecycle(self, session_id, offer_lifecycle):
        """Update the offer lifecycle state."""
        with self.lock:
            if session_id in self.sessions:
                state_dict = offer_lifecycle.to_dict() if hasattr(offer_lifecycle, 'to_dict') else offer_lifecycle
                self.sessions[session_id]['offer_lifecycle'] = state_dict
                return True
        return False

    def calculate_offer_improvement(self, session_id, current_offer, trigger, context=None):
        """
        Calculate if and how an offer should improve.
        Returns improved offer terms or None if no improvement.
        """
        offer_lifecycle = self.get_offer_lifecycle(session_id)
        if not offer_lifecycle:
            return None

        return offer_lifecycle.calculate_improvement(current_offer, trigger, context)

    def check_offer_expiration(self, session_id, offer_id):
        """
        Check if an offer has expired and should be withdrawn.
        Returns (is_expired, reason).
        """
        offer_lifecycle = self.get_offer_lifecycle(session_id)
        deal_mode = self.get_deal_mode(session_id)

        if not offer_lifecycle or not deal_mode:
            return False, None

        for offer in deal_mode.pending_offers:
            if offer.get('id') == offer_id:
                is_expired, reason = offer_lifecycle.check_expiration(offer)
                if is_expired:
                    # Mark as expired
                    offer['status'] = 'expired'
                    self.update_deal_mode(session_id, deal_mode)
                return is_expired, reason

        return False, None

    def extend_offer(self, session_id, offer_id, duration_seconds=60):
        """Extend an offer's expiration time."""
        deal_mode = self.get_deal_mode(session_id)
        if not deal_mode:
            return False

        for offer in deal_mode.pending_offers:
            if offer.get('id') == offer_id:
                offer['expires_at'] = time.time() + duration_seconds
                self.update_deal_mode(session_id, deal_mode)
                return True

        return False

    # =========================================================================
    # Deal Resolution
    # =========================================================================

    def resolve_deal(self, session_id, accepted_offer):
        """
        Resolve a deal and generate post-deal events.
        Returns list of events (shark reactions, recap, etc.)
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                return []

        # Create resolution and process
        resolution = DealResolution(session)
        events = resolution.resolve_deal(session, accepted_offer)

        # Update session with resolution data
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['deal_resolution'] = {
                    'accepted_offer': accepted_offer,
                    'events': events,
                    'resolved_at': int(time.time() * 1000)
                }
                self.sessions[session_id]['finalDeal'] = accepted_offer
                self.sessions[session_id]['phase'] = 'closed'

                # Update deal mode to closed
                deal_mode = self.sessions[session_id].get('deal_mode', {})
                if isinstance(deal_mode, dict):
                    deal_mode['current_mode'] = 'closed'
                self.sessions[session_id]['deal_mode'] = deal_mode

        return events

    def get_deal_resolution(self, session_id):
        """Get the deal resolution data for a session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return session.get('deal_resolution')
        return None

    # =========================================================================
    # Founder Message Processing
    # =========================================================================

    def process_founder_message(self, session_id, message):
        """
        Process a founder's message to update all shark belief states.
        Returns dict of {shark_id: [proofs_satisfied]} for each shark.
        """
        results = {}

        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                return results

            for shark_id, shark_data in session['sharks'].items():
                if shark_data.get('status') != 'live':
                    continue

                # Get belief state and process message
                belief_state = InvestorBeliefState.from_dict(shark_data.get('belief_state', {}))
                proofs_satisfied = belief_state.process_founder_message(message)

                # Update belief state
                shark_data['belief_state'] = belief_state.to_dict()
                results[shark_id] = proofs_satisfied

        return results

    def notify_sharks_of_competing_offer(self, session_id, new_offer):
        """
        Notify all live sharks of a new competing offer.
        Updates their belief states with the competing offer info.
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                return

            for shark_id, shark_data in session['sharks'].items():
                if shark_data.get('status') != 'live':
                    continue
                if shark_id == new_offer.get('sharkId'):
                    continue  # Don't notify the shark who made the offer

                # Get belief state and update with competing offer
                belief_state = InvestorBeliefState.from_dict(shark_data.get('belief_state', {}))
                belief_state.see_competing_offer(new_offer)
                shark_data['belief_state'] = belief_state.to_dict()

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
