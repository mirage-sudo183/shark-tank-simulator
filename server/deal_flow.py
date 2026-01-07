"""
Deal Flow Management for Shark Tank Simulator
Handles proof tracking, offer progression, deal modes, and resolution
"""

import time
import re
import random
import uuid
from typing import Dict, List, Optional, Tuple, Any


# =============================================================================
# Proof Tracker - Validates conditions and tracks what founder has proven
# =============================================================================

class ProofTracker:
    """Explicit proof flag system for condition validation."""

    PROOF_TYPES = {
        'revenue': {
            'keywords': ['revenue', 'sales', 'arr', 'mrr', 'making', 'earning', 'profit'],
            'numeric': True,
            'unit_multipliers': {'k': 1000, 'm': 1000000, 'million': 1000000, 'thousand': 1000}
        },
        'users': {
            'keywords': ['users', 'customers', 'subscribers', 'members', 'signups', 'downloads'],
            'numeric': True,
            'unit_multipliers': {'k': 1000, 'm': 1000000, 'million': 1000000, 'thousand': 1000}
        },
        'patents': {
            'keywords': ['patent', 'patented', 'ip', 'intellectual property', 'protected', 'trademark'],
            'numeric': False,
            'unit_multipliers': {}
        },
        'team': {
            'keywords': ['team', 'experience', 'years', 'background', 'worked at', 'founded'],
            'numeric': False,
            'unit_multipliers': {}
        },
        'traction': {
            'keywords': ['growth', 'growing', 'retention', 'engagement', 'month over month', 'yoy'],
            'numeric': True,
            'unit_multipliers': {'%': 1, 'percent': 1}
        },
        'partnerships': {
            'keywords': ['partnership', 'deal', 'contract', 'agreement', 'signed', 'working with'],
            'numeric': False,
            'unit_multipliers': {}
        },
        'product': {
            'keywords': ['prototype', 'mvp', 'launched', 'live', 'shipping', 'in production'],
            'numeric': False,
            'unit_multipliers': {}
        }
    }

    def __init__(self):
        self.required_proofs: Dict[str, Dict] = {}  # {proof_type: {threshold, satisfied, asked_at}}
        self.provided_proofs: Dict[str, Dict] = {}  # {proof_type: {value, timestamp}}
        self.proof_history: List[Dict] = []  # Timeline of all proofs

    def require_proof(self, proof_type: str, threshold: Optional[float] = None,
                      reason: str = None) -> None:
        """Shark requires specific proof before investing."""
        if proof_type not in self.PROOF_TYPES:
            return

        self.required_proofs[proof_type] = {
            'threshold': threshold,
            'satisfied': False,
            'asked_at': time.time(),
            'reason': reason or f"Need to see {proof_type}"
        }

    def check_message_for_proofs(self, message: str) -> List[Tuple[str, Any]]:
        """Scan founder message for proof signals."""
        message_lower = message.lower()
        proofs_found = []

        for proof_type, config in self.PROOF_TYPES.items():
            if any(kw in message_lower for kw in config['keywords']):
                if config['numeric']:
                    value = self._extract_numeric(message, config.get('unit_multipliers', {}))
                else:
                    value = True

                if value is not None:
                    proofs_found.append((proof_type, value))

        return proofs_found

    def _extract_numeric(self, text: str, unit_multipliers: Dict[str, int]) -> Optional[float]:
        """Extract numeric value from text with unit handling."""
        # Patterns: $500K, 500k, 500,000, 500 thousand, 2.5 million, 50%
        patterns = [
            r'\$?([\d,]+(?:\.\d+)?)\s*(?:million|m)\b',  # millions
            r'\$?([\d,]+(?:\.\d+)?)\s*(?:thousand|k)\b',  # thousands
            r'\$?([\d,]+(?:\.\d+)?)\s*%',  # percentages
            r'\$?([\d,]+(?:\.\d+)?)\b',  # plain numbers
        ]

        multipliers = [1000000, 1000, 1, 1]

        for pattern, multiplier in zip(patterns, multipliers):
            match = re.search(pattern, text.lower())
            if match:
                try:
                    value = float(match.group(1).replace(',', ''))
                    return value * multiplier
                except ValueError:
                    continue

        return None

    def satisfy_proof(self, proof_type: str, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Mark proof as satisfied and check against threshold.
        Returns (satisfied, reason).
        """
        # Record the proof regardless
        self.provided_proofs[proof_type] = {
            'value': value,
            'timestamp': time.time()
        }
        self.proof_history.append({
            'type': proof_type,
            'value': value,
            'timestamp': time.time()
        })

        # Check if it was required
        if proof_type not in self.required_proofs:
            return True, f"Noted: {proof_type} = {value}"

        req = self.required_proofs[proof_type]

        # Check threshold if numeric
        if req['threshold'] is not None:
            if isinstance(value, (int, float)) and value >= req['threshold']:
                req['satisfied'] = True
                return True, f"Satisfied: {proof_type} ({value} >= {req['threshold']})"
            elif isinstance(value, (int, float)):
                return False, f"Below threshold: {proof_type} ({value} < {req['threshold']})"
        else:
            # Non-numeric proof - just having it is enough
            req['satisfied'] = True
            return True, f"Satisfied: {proof_type}"

        return False, None

    def get_unsatisfied_proofs(self) -> List[Dict]:
        """Get list of still-required proofs with details."""
        return [
            {'type': p, **r}
            for p, r in self.required_proofs.items()
            if not r['satisfied']
        ]

    def can_make_unconditional_offer(self) -> bool:
        """All required proofs must be satisfied."""
        return len(self.get_unsatisfied_proofs()) == 0

    def get_proof_summary(self) -> Dict:
        """Get summary of proof status."""
        return {
            'required': list(self.required_proofs.keys()),
            'satisfied': [p for p, r in self.required_proofs.items() if r['satisfied']],
            'unsatisfied': [p for p, r in self.required_proofs.items() if not r['satisfied']],
            'provided': self.provided_proofs
        }

    def to_dict(self) -> Dict:
        """Serialize for storage."""
        return {
            'required_proofs': self.required_proofs,
            'provided_proofs': self.provided_proofs,
            'proof_history': self.proof_history
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProofTracker':
        """Deserialize from storage."""
        tracker = cls()
        tracker.required_proofs = data.get('required_proofs', {})
        tracker.provided_proofs = data.get('provided_proofs', {})
        tracker.proof_history = data.get('proof_history', [])
        return tracker


# =============================================================================
# Offer Progression - Tracks offer history and enforces logical progression
# =============================================================================

class OfferProgression:
    """Tracks offer history and enforces logical progression."""

    MAX_IMPROVEMENT_PER_ROUND = 0.20  # 20% max improvement per negotiation round
    MIN_IMPROVEMENT_PER_ROUND = 0.02  # 2% minimum improvement if improving

    def __init__(self, shark_id: str, initial_ask_valuation: float):
        self.shark_id = shark_id
        self.initial_ask_valuation = initial_ask_valuation
        self.offers: List[Dict] = []  # History of offers made
        self.valuation_floor: float = initial_ask_valuation * 0.3  # Won't go below 30%
        self.valuation_ceiling: float = initial_ask_valuation * 1.2  # Won't exceed 120%
        self.negotiation_round: int = 0
        self.rejection_count: int = 0
        self.counter_count: int = 0

    def set_valuation_bounds(self, floor_multiplier: float, ceiling_multiplier: float):
        """Set valuation bounds based on investor archetype."""
        self.valuation_floor = self.initial_ask_valuation * floor_multiplier
        self.valuation_ceiling = self.initial_ask_valuation * ceiling_multiplier

    def get_next_offer_constraints(self) -> Dict:
        """Returns bounds for next offer based on history."""
        if not self.offers:
            return {
                'min_valuation': self.valuation_floor,
                'max_valuation': self.valuation_ceiling,
                'must_improve': False,
                'suggested_valuation': (self.valuation_floor + self.valuation_ceiling) / 2,
                'negotiation_round': 0
            }

        last_offer = self.offers[-1]
        last_valuation = last_offer['implied_valuation']

        # Calculate improvement bounds
        min_improvement = last_valuation * (1 + self.MIN_IMPROVEMENT_PER_ROUND)
        max_improvement = min(
            last_valuation * (1 + self.MAX_IMPROVEMENT_PER_ROUND),
            self.valuation_ceiling
        )

        # Suggested valuation based on how many rounds
        # Each rejection should prompt better terms
        improvement_factor = 1 + (0.05 * self.rejection_count) + (0.03 * self.counter_count)
        suggested = min(last_valuation * improvement_factor, self.valuation_ceiling)

        return {
            'min_valuation': self.valuation_floor,
            'max_valuation': max_improvement,
            'last_valuation': last_valuation,
            'must_improve': self.negotiation_round > 0 and self.rejection_count == 0,
            'suggested_valuation': suggested,
            'negotiation_round': self.negotiation_round + 1
        }

    def record_offer(self, offer: Dict) -> Tuple[bool, Optional[str]]:
        """Record offer and validate it follows progression rules."""
        constraints = self.get_next_offer_constraints()
        implied_val = offer.get('implied_valuation', 0)

        # Validate against constraints
        if constraints.get('must_improve') and implied_val <= constraints.get('last_valuation', 0):
            return False, "Offer must improve on previous valuation"

        if implied_val < self.valuation_floor:
            return False, f"Valuation below floor ({self.valuation_floor:,.0f})"

        if implied_val > self.valuation_ceiling:
            return False, f"Valuation above ceiling ({self.valuation_ceiling:,.0f})"

        # Record the offer
        offer['round'] = self.negotiation_round
        offer['timestamp'] = time.time()
        self.offers.append(offer)
        self.negotiation_round += 1

        return True, None

    def record_rejection(self):
        """Record that founder rejected/declined."""
        self.rejection_count += 1

    def record_counter(self):
        """Record that founder countered."""
        self.counter_count += 1

    def get_best_offer(self) -> Optional[Dict]:
        """Get the best offer made so far (highest valuation)."""
        if not self.offers:
            return None
        return max(self.offers, key=lambda o: o.get('implied_valuation', 0))

    def to_dict(self) -> Dict:
        """Serialize for storage."""
        return {
            'shark_id': self.shark_id,
            'initial_ask_valuation': self.initial_ask_valuation,
            'offers': self.offers,
            'valuation_floor': self.valuation_floor,
            'valuation_ceiling': self.valuation_ceiling,
            'negotiation_round': self.negotiation_round,
            'rejection_count': self.rejection_count,
            'counter_count': self.counter_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OfferProgression':
        """Deserialize from storage."""
        prog = cls(data['shark_id'], data['initial_ask_valuation'])
        prog.offers = data.get('offers', [])
        prog.valuation_floor = data.get('valuation_floor', prog.valuation_floor)
        prog.valuation_ceiling = data.get('valuation_ceiling', prog.valuation_ceiling)
        prog.negotiation_round = data.get('negotiation_round', 0)
        prog.rejection_count = data.get('rejection_count', 0)
        prog.counter_count = data.get('counter_count', 0)
        return prog


# =============================================================================
# Deal Mode - Manages negotiation phases and competitive dynamics
# =============================================================================

class DealMode:
    """Manages deal negotiation mode and competitive dynamics."""

    MODES = {
        'exploration': {
            'description': 'Sharks asking questions, no offers yet',
            'can_offer': True,
            'can_accept': False,
            'can_counter': False,
            'competitive_bidding': False
        },
        'single_offer': {
            'description': 'One shark has made an offer',
            'can_offer': True,  # Others can still offer
            'can_accept': True,
            'can_counter': True,
            'timeout': 90,  # Seconds before mode can escalate
            'competitive_bidding': False
        },
        'bidding_war': {
            'description': 'Multiple competing offers on the table',
            'can_offer': True,
            'can_accept': True,
            'can_counter': True,
            'competitive_bidding': True,
            'show_comparison': True
        },
        'final_offer': {
            'description': 'Founder signaling intent to accept - last chance',
            'can_offer': True,  # Others can still jump in
            'can_accept': True,
            'can_counter': False,  # No more countering, decision time
            'countdown': 30,
            'competitive_bidding': True
        },
        'closed': {
            'description': 'Deal accepted or all sharks out',
            'can_offer': False,
            'can_accept': False,
            'can_counter': False,
            'competitive_bidding': False
        }
    }

    def __init__(self):
        self.current_mode = 'exploration'
        self.pending_offers: List[Dict] = []  # Active offers
        self.accepting_offer_id: Optional[str] = None
        self.final_countdown_start: Optional[float] = None
        self.mode_history: List[Dict] = []

    def get_mode_config(self) -> Dict:
        """Get current mode configuration."""
        return self.MODES.get(self.current_mode, self.MODES['exploration'])

    def add_offer(self, offer: Dict) -> Dict:
        """Add an offer and update mode accordingly."""
        self.pending_offers.append(offer)

        events = []

        # Transition based on offer count
        if self.current_mode == 'exploration':
            self._transition_to('single_offer')
            events.append({
                'type': 'mode_change',
                'new_mode': 'single_offer',
                'message': f"{offer['sharkName']} makes the first offer!"
            })
        elif self.current_mode == 'single_offer' and len(self.pending_offers) > 1:
            self._transition_to('bidding_war')
            events.append({
                'type': 'mode_change',
                'new_mode': 'bidding_war',
                'message': "Multiple offers! A bidding war begins!"
            })
        elif self.current_mode == 'final_offer':
            # Someone jumped in during final countdown!
            events.append({
                'type': 'final_offer_interrupted',
                'shark_id': offer['sharkId'],
                'message': f"{offer['sharkName']} jumps in at the last second!"
            })
            self._transition_to('bidding_war')

        return {'events': events, 'mode': self.current_mode}

    def remove_offer(self, offer_id: str) -> None:
        """Remove an offer (declined, expired, or withdrawn)."""
        self.pending_offers = [o for o in self.pending_offers if o.get('id') != offer_id]

        # Check if we need to downgrade mode
        if len(self.pending_offers) == 0:
            self._transition_to('exploration')
        elif len(self.pending_offers) == 1 and self.current_mode == 'bidding_war':
            self._transition_to('single_offer')

    def initiate_final_offer(self, offer_id: str) -> Dict:
        """Founder signals intent to accept - starts final countdown."""
        self.accepting_offer_id = offer_id
        self.final_countdown_start = time.time()
        self._transition_to('final_offer')

        return {
            'type': 'final_offer_countdown',
            'offer_id': offer_id,
            'countdown': self.MODES['final_offer']['countdown'],
            'message': "Going once... Other sharks, this is your last chance!"
        }

    def check_final_countdown(self) -> Optional[Dict]:
        """Check if final countdown has expired."""
        if self.current_mode != 'final_offer':
            return None

        if self.final_countdown_start is None:
            return None

        elapsed = time.time() - self.final_countdown_start
        countdown = self.MODES['final_offer']['countdown']

        if elapsed >= countdown:
            return {
                'type': 'final_countdown_expired',
                'offer_id': self.accepting_offer_id,
                'message': "Time's up! The deal is done!"
            }

        return {
            'type': 'countdown_tick',
            'remaining': int(countdown - elapsed),
            'offer_id': self.accepting_offer_id
        }

    def close_deal(self, accepted_offer: Dict) -> Dict:
        """Close the deal."""
        self._transition_to('closed')
        self.accepting_offer_id = accepted_offer.get('id')

        return {
            'type': 'deal_closed',
            'offer': accepted_offer,
            'final_mode': 'closed'
        }

    def get_competing_offers(self, exclude_shark_id: str = None) -> List[Dict]:
        """Get offers from other sharks."""
        return [
            o for o in self.pending_offers
            if o.get('sharkId') != exclude_shark_id
        ]

    def get_best_competing_offer(self, exclude_shark_id: str = None) -> Optional[Dict]:
        """Get the best offer from competitors."""
        competing = self.get_competing_offers(exclude_shark_id)
        if not competing:
            return None
        return max(competing, key=lambda o: o.get('implied_valuation', 0))

    def _transition_to(self, new_mode: str) -> None:
        """Transition to a new mode."""
        self.mode_history.append({
            'from': self.current_mode,
            'to': new_mode,
            'timestamp': time.time()
        })
        self.current_mode = new_mode

        # Reset countdown if leaving final_offer
        if new_mode != 'final_offer':
            self.final_countdown_start = None
            self.accepting_offer_id = None

    def to_dict(self) -> Dict:
        """Serialize for storage."""
        return {
            'current_mode': self.current_mode,
            'pending_offers': self.pending_offers,
            'accepting_offer_id': self.accepting_offer_id,
            'final_countdown_start': self.final_countdown_start,
            'mode_history': self.mode_history
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DealMode':
        """Deserialize from storage."""
        mode = cls()
        mode.current_mode = data.get('current_mode', 'exploration')
        mode.pending_offers = data.get('pending_offers', [])
        mode.accepting_offer_id = data.get('accepting_offer_id')
        mode.final_countdown_start = data.get('final_countdown_start')
        mode.mode_history = data.get('mode_history', [])
        return mode


# =============================================================================
# Offer Lifecycle - Rules for when offers expire or improve
# =============================================================================

class OfferLifecycle:
    """Rules for when offers expire or improve."""

    BASE_DURATION = 300  # 5 minutes - reasonable time to consider an offer
    EXTENSION_ON_COUNTER = 120  # 2 minutes extension when countering
    EXTENSION_ON_COMPETING = 120  # 2 minutes when competing offer made
    MIN_DURATION = 180  # 3 minutes minimum

    IMPROVEMENT_TRIGGERS = {
        'proof_satisfied': {
            'valuation_boost': 1.10,  # 10% better valuation
            'description': 'Founder provided requested proof'
        },
        'competing_offer_better': {
            'valuation_boost': 1.05,  # 5% to beat competitor
            'description': 'Must beat competing offer'
        },
        'strong_answer': {
            'valuation_boost': 1.05,  # 5% for impressive response
            'description': 'Founder gave compelling answer'
        },
        'multiple_sharks_interested': {
            'valuation_boost': 1.08,  # 8% due to competition
            'description': 'Competition driving up price'
        }
    }

    EXPIRATION_BEHAVIORS = {
        'high_conviction': {
            'withdraw_chance': 0.2,  # 20% chance to withdraw
            'out_chance': 0.1,  # 10% chance to go out
            'extend_chance': 0.7,  # 70% chance to extend
        },
        'medium_conviction': {
            'withdraw_chance': 0.4,
            'out_chance': 0.2,
            'extend_chance': 0.4,
        },
        'low_conviction': {
            'withdraw_chance': 0.3,
            'out_chance': 0.5,
            'extend_chance': 0.2,
        }
    }

    def __init__(self):
        self.offer_timers: Dict[str, Dict] = {}  # offer_id -> {created, duration, extensions}

    def start_offer_timer(self, offer_id: str, shark_conviction: str = 'medium') -> Dict:
        """Start timer for an offer."""
        # Higher conviction = longer patience
        conviction_bonus = {
            'high': 120,  # 2 minutes extra for high conviction
            'medium': 0,
            'low': -60  # 1 minute less for low conviction (but still min 3 min)
        }.get(shark_conviction, 0)

        duration = max(self.MIN_DURATION, self.BASE_DURATION + conviction_bonus)

        self.offer_timers[offer_id] = {
            'created': time.time(),
            'duration': duration,
            'extensions': 0,
            'conviction': shark_conviction
        }

        return {
            'offer_id': offer_id,
            'duration': duration,
            'expires_at': time.time() + duration
        }

    def extend_offer(self, offer_id: str, reason: str) -> Optional[Dict]:
        """Extend an offer's duration."""
        if offer_id not in self.offer_timers:
            return None

        timer = self.offer_timers[offer_id]

        extension = {
            'counter': self.EXTENSION_ON_COUNTER,
            'competing': self.EXTENSION_ON_COMPETING,
        }.get(reason, 20)

        timer['duration'] += extension
        timer['extensions'] += 1

        return {
            'offer_id': offer_id,
            'extended_by': extension,
            'new_duration': timer['duration'],
            'total_extensions': timer['extensions']
        }

    def check_expiration(self, offer_id: str) -> Dict:
        """Check if offer has expired and determine outcome."""
        if offer_id not in self.offer_timers:
            return {'expired': False}

        timer = self.offer_timers[offer_id]
        elapsed = time.time() - timer['created']

        if elapsed < timer['duration']:
            return {
                'expired': False,
                'remaining': int(timer['duration'] - elapsed)
            }

        # Offer expired - determine behavior based on conviction
        conviction = timer.get('conviction', 'medium')
        behavior = self.EXPIRATION_BEHAVIORS.get(conviction, self.EXPIRATION_BEHAVIORS['medium'])

        roll = random.random()
        if roll < behavior['out_chance']:
            outcome = 'out'
        elif roll < behavior['out_chance'] + behavior['withdraw_chance']:
            outcome = 'withdraw'
        else:
            outcome = 'extend'

        return {
            'expired': True,
            'outcome': outcome,
            'conviction': conviction
        }

    def calculate_improvement(self, current_offer: Dict, trigger: str,
                              context: Dict = None) -> Optional[Dict]:
        """Calculate improved offer terms based on trigger."""
        if trigger not in self.IMPROVEMENT_TRIGGERS:
            return None

        trigger_config = self.IMPROVEMENT_TRIGGERS[trigger]
        boost = trigger_config['valuation_boost']

        current_val = current_offer.get('implied_valuation', 0)
        new_val = int(current_val * boost)

        # Recalculate equity
        amount = current_offer.get('amount', 100000)
        new_equity = round((amount / new_val) * 100, 1)

        return {
            'amount': amount,
            'equity': new_equity,
            'implied_valuation': new_val,
            'improvement_trigger': trigger,
            'improvement_reason': trigger_config['description'],
            'previous_valuation': current_val,
            'valuation_increase': new_val - current_val
        }

    def should_improve_offer(self, shark_state: Dict, trigger: str,
                             context: Dict = None) -> Tuple[bool, Optional[float]]:
        """Determine if shark should improve their offer."""
        if trigger == 'proof_satisfied':
            proof_tracker = shark_state.get('proof_tracker')
            if proof_tracker and proof_tracker.can_make_unconditional_offer():
                return True, self.IMPROVEMENT_TRIGGERS[trigger]['valuation_boost']

        elif trigger == 'competing_offer_better':
            best_competing = context.get('best_competing_offer') if context else None
            last_offer = shark_state.get('last_offer')
            if best_competing and last_offer:
                if best_competing.get('implied_valuation', 0) > last_offer.get('implied_valuation', 0):
                    return True, self.IMPROVEMENT_TRIGGERS[trigger]['valuation_boost']

        elif trigger == 'strong_answer':
            conviction = shark_state.get('belief_state', {}).get('capital_conviction', 'low')
            if conviction in ['medium', 'high']:
                return True, self.IMPROVEMENT_TRIGGERS[trigger]['valuation_boost']

        elif trigger == 'multiple_sharks_interested':
            active_sharks = context.get('active_shark_count', 1) if context else 1
            if active_sharks >= 3:
                return True, self.IMPROVEMENT_TRIGGERS[trigger]['valuation_boost']

        return False, None

    def to_dict(self) -> Dict:
        return {'offer_timers': self.offer_timers}

    @classmethod
    def from_dict(cls, data: Dict) -> 'OfferLifecycle':
        lifecycle = cls()
        lifecycle.offer_timers = data.get('offer_timers', {})
        return lifecycle


# =============================================================================
# Deal Resolution - Clean post-deal flow with recap and reactions
# =============================================================================

class DealResolution:
    """Clean post-deal flow with recap and reactions."""

    SHARK_REACTIONS = {
        'gracious': [
            "Congratulations! You made a great choice.",
            "Well done. {winner} will take good care of you.",
            "Smart decision. Best of luck to you both!",
        ],
        'regretful': [
            "I wish we could have worked together. Good luck!",
            "You're leaving money on the table, but I respect your decision.",
            "I really wanted this one. {winner} is lucky.",
        ],
        'competitive': [
            "I think you're making a mistake, but it's your company.",
            "{winner} got a good deal. Maybe too good.",
            "Fine. But remember my offer when things get tough.",
        ],
        'relieved': [
            "Honestly, I think {winner} is a better fit for you.",
            "Good luck! I hope it works out.",
            "That's probably for the best.",
        ]
    }

    def resolve_deal(self, session: Dict, accepted_offer: Dict) -> List[Dict]:
        """Handle deal acceptance with proper resolution."""
        events = []

        winner_id = accepted_offer.get('sharkId')
        winner_name = accepted_offer.get('sharkName')

        # 1. Announce acceptance with celebration
        events.append({
            'type': 'deal_accepted',
            'offer': accepted_offer,
            'shark_id': winner_id,
            'message': f"We have a deal! {winner_name} invests ${accepted_offer.get('amount', 0):,} for {accepted_offer.get('equity', 0)}%!"
        })

        # 2. Other sharks react
        sharks = session.get('sharks', {})
        for shark_id, shark_state in sharks.items():
            if shark_id == winner_id:
                continue

            if shark_state.get('status') == 'out':
                continue

            reaction = self._generate_shark_reaction(
                shark_id,
                shark_state,
                accepted_offer
            )

            events.append({
                'type': 'shark_reaction',
                'shark_id': shark_id,
                'shark_name': shark_state.get('name', shark_id),
                'message': reaction['message'],
                'tone': reaction['tone']
            })

        # 3. Deal recap
        events.append({
            'type': 'deal_recap',
            'final_terms': self._format_final_terms(accepted_offer),
            'valuation': accepted_offer.get('implied_valuation', 0),
            'deal_type': accepted_offer.get('deal_type', 'cash_equity'),
            'conditions': accepted_offer.get('conditions', [])
        })

        # 4. Negotiation summary
        events.append({
            'type': 'negotiation_summary',
            'all_offers': self._get_all_offers_summary(session),
            'questions_answered': self._count_qa(session),
            'duration_seconds': int(time.time() - session.get('createdAt', time.time()) / 1000)
        })

        return events

    def resolve_no_deal(self, session: Dict, reason: str) -> List[Dict]:
        """Handle when no deal is made."""
        events = []

        events.append({
            'type': 'no_deal',
            'reason': reason,
            'message': "No deal today. Thank you for your time."
        })

        # Summary of what happened
        events.append({
            'type': 'session_summary',
            'offers_received': len(session.get('offers', [])),
            'best_offer': self._get_best_offer(session),
            'sharks_out': self._count_sharks_out(session)
        })

        return events

    def _generate_shark_reaction(self, shark_id: str, state: Dict,
                                  winning_offer: Dict) -> Dict:
        """Generate appropriate reaction based on context."""
        winner_name = winning_offer.get('sharkName', 'they')

        # Determine tone
        made_offer = bool(state.get('offers_made'))
        conviction = state.get('belief_state', {}).get('capital_conviction', 'low')

        if made_offer and conviction == 'high':
            tone = 'regretful'
        elif made_offer:
            tone = 'competitive'
        elif conviction == 'low':
            tone = 'relieved'
        else:
            tone = 'gracious'

        message = random.choice(self.SHARK_REACTIONS[tone])
        message = message.format(winner=winner_name)

        return {'tone': tone, 'message': message}

    def _format_final_terms(self, offer: Dict) -> Dict:
        """Format final deal terms for display."""
        terms = {
            'amount': f"${offer.get('amount', 0):,}",
            'equity': f"{offer.get('equity', 0)}%",
            'valuation': f"${offer.get('implied_valuation', 0):,}",
            'deal_type': offer.get('deal_type', 'cash_equity')
        }

        if offer.get('royalty'):
            terms['royalty'] = f"${offer['royalty']}/unit until ${offer.get('royaltyUntil', 0):,}"

        if offer.get('conditions'):
            terms['conditions'] = offer['conditions']

        return terms

    def _get_all_offers_summary(self, session: Dict) -> List[Dict]:
        """Get summary of all offers made."""
        offers = session.get('offers', [])
        return [
            {
                'shark': o.get('sharkName'),
                'amount': o.get('amount'),
                'equity': o.get('equity'),
                'valuation': o.get('implied_valuation'),
                'status': o.get('status')
            }
            for o in offers
        ]

    def _get_best_offer(self, session: Dict) -> Optional[Dict]:
        """Get the best offer that was made."""
        offers = session.get('offers', [])
        if not offers:
            return None
        return max(offers, key=lambda o: o.get('implied_valuation', 0))

    def _count_qa(self, session: Dict) -> int:
        """Count Q&A exchanges."""
        transcript = session.get('qaTranscript', [])
        return len([m for m in transcript if not m.get('isShark')])

    def _count_sharks_out(self, session: Dict) -> int:
        """Count how many sharks went out."""
        sharks = session.get('sharks', {})
        return len([s for s in sharks.values() if s.get('status') == 'out'])


# =============================================================================
# Global instances for session management
# =============================================================================

def create_deal_flow_state(pitch_data: Dict) -> Dict:
    """Create initial deal flow state for a session."""
    amount = pitch_data.get('amountRaising', 100000)
    equity = pitch_data.get('equityPercent', 10)
    initial_valuation = amount / (equity / 100) if equity > 0 else amount * 10

    return {
        'deal_mode': DealMode().to_dict(),
        'offer_lifecycle': OfferLifecycle().to_dict(),
        'initial_valuation': initial_valuation
    }
