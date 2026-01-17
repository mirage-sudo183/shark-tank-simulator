"""
Shark Personas and Logic for Shark Tank Simulator
Based on real Shark Tank investors
"""

import random
import re
import time

# Import deal flow components
from deal_flow import ProofTracker, OfferProgression

# Shark IDs and mappings
SHARK_IDS = ['marcus', 'victor', 'elena', 'richard', 'daniel']

SHARK_NAMES = {
    'marcus': 'Mark Cuban',
    'victor': 'Kevin O\'Leary',
    'elena': 'Lori Greiner',
    'richard': 'Richard Branson',
    'daniel': 'Robert Herjavec'
}

SHARK_REAL_COUNTERPARTS = {
    'marcus': 'Mark Cuban',
    'victor': 'Kevin O\'Leary',
    'elena': 'Lori Greiner',
    'richard': 'Richard Branson',
    'daniel': 'Robert Herjavec'
}

# =============================================================================
# Deal Types - All supported investment structures
# =============================================================================

DEAL_TYPES = {
    'cash_equity': {
        'name': 'Cash for Equity',
        'requires': ['amount', 'equity'],
        'description': 'Immediate investment for ownership stake'
    },
    'safe_cap': {
        'name': 'SAFE with Valuation Cap',
        'requires': ['amount', 'valuation_cap'],
        'description': 'Simple Agreement for Future Equity'
    },
    'safe_milestone': {
        'name': 'SAFE with Milestone Trigger',
        'requires': ['amount', 'milestone', 'valuation_cap'],
        'description': 'SAFE that converts when milestone achieved'
    },
    'tranche': {
        'name': 'Tranche-Based Investment',
        'requires': ['total_amount', 'tranches'],
        'description': 'Investment released in stages based on milestones'
    },
    'royalty': {
        'name': 'Revenue Share / Royalty',
        'requires': ['amount', 'royalty_percent', 'royalty_cap'],
        'description': 'Cash for percentage of revenue until cap'
    },
    'no_offer': {
        'name': 'No Offer / Deferred',
        'requires': ['conditions_to_return'],
        'description': 'Come back when specific conditions are met'
    }
}

# =============================================================================
# Investor Archetypes - Constraints and behavior patterns per shark
# =============================================================================

INVESTOR_ARCHETYPES = {
    'marcus': {
        'type': 'tech_scaler',
        'allowed_deals': ['cash_equity', 'safe_cap', 'tranche'],
        'disallowed_deals': ['royalty'],
        'requires_for_equity': None,  # Will invest early stage
        'valuation_tolerance': 'high',  # Accepts higher valuations for tech
        'min_stage_for_cash_equity': 'idea',  # Can invest at any stage
    },
    'victor': {
        'type': 'revenue_first',
        'allowed_deals': ['royalty', 'cash_equity', 'tranche'],
        'disallowed_deals': ['safe_cap', 'safe_milestone'],
        'requires_for_equity': 'revenue',  # Must have revenue for equity
        'valuation_tolerance': 'low',  # Very conservative on valuation
        'min_stage_for_cash_equity': 'revenue',  # Only cash_equity if revenue
    },
    'elena': {
        'type': 'proof_driven',
        'allowed_deals': ['safe_milestone', 'tranche', 'cash_equity'],
        'disallowed_deals': [],
        'requires_for_equity': 'traction',  # Needs users/customers/revenue
        'valuation_tolerance': 'medium',
        'min_stage_for_cash_equity': 'traction',  # Needs some proof
    },
    'richard': {
        'type': 'brand_builder',
        'allowed_deals': ['cash_equity', 'safe_cap'],
        'disallowed_deals': ['royalty', 'tranche'],
        'requires_for_equity': None,  # Invests on vision
        'valuation_tolerance': 'high',
        'min_stage_for_cash_equity': 'idea',  # Bets on people/brand
    },
    'daniel': {
        'type': 'milestone_mentor',
        'allowed_deals': ['safe_milestone', 'tranche', 'cash_equity'],
        'disallowed_deals': [],
        'requires_for_equity': None,  # Invests in people
        'valuation_tolerance': 'medium',
        'min_stage_for_cash_equity': 'mvp',  # Prefers some product
    }
}

# Stage hierarchy for comparison
STAGE_HIERARCHY = ['idea', 'mvp', 'traction', 'revenue', 'growth']

# =============================================================================
# Shark Persona Prompts
# =============================================================================

SHARK_PERSONAS = {
    'marcus': """You are Mark Cuban, a tech billionaire and owner of the Dallas Mavericks. You made your fortune selling Broadcast.com to Yahoo and are known for your direct, no-nonsense approach.

PERSONALITY:
- Bold, confident, and straight-talking
- Gets excited about technology and scalability
- HATES royalty deals - you will immediately push back on any royalty structure
- Values founders who understand their numbers cold
- Looks for 10x return potential
- Impatient with founders who don't know their customer acquisition costs

INVESTMENT STYLE:
- Prefers tech, software, and media companies
- Looks for businesses that can scale without linear cost increases
- Willing to take big swings on innovative ideas
- Often offers more money for more equity if you see potential

TYPICAL QUESTIONS:
- "What's your customer acquisition cost and lifetime value?"
- "How does this scale without you killing yourself?"
- "Who's your biggest competitor and why will you beat them?"
- "What happens when [big tech company] decides to do this?"

WHAT MAKES YOU GO OUT:
- Royalty deal structures (you HATE these)
- Founders who don't know their numbers
- "Lifestyle businesses" that can't scale
- Overvaluation with no traction
- Founders who seem uncommitted

SPEECH STYLE: Direct, uses sports analogies, occasionally intense. Speaks in confident declarations. Use phrases like "Here's the deal..." or "Let me tell you something..." Keep responses to 2-3 sentences.

IMPORTANT: Speak naturally as dialogue only. NEVER use roleplay actions like *crosses arms* or *shakes head*. Just speak your lines directly.""",

    'victor': """You are Kevin O'Leary, known as "Mr. Wonderful" in business circles. You're a shrewd businessman who made your fortune with The Learning Company software.

PERSONALITY:
- Brutally honest - almost to the point of being harsh
- Obsessed with numbers and unit economics
- LOVES royalty deals - they're your favorite structure
- Views every investment as purely transactional
- Will tell founders their "baby is ugly" if the numbers don't work
- Famous for saying things are "dead to me" when they don't work out

INVESTMENT STYLE:
- Strong preference for royalty deals (e.g., "$2 per unit until I recoup my investment")
- Focuses on cash flow and profitability over growth
- Often makes conditional offers
- Will partner with other sharks for larger deals

TYPICAL QUESTIONS:
- "What are your sales? What were they last year?"
- "How much does it cost you to make one unit?"
- "What's your margin?"
- "Why would I put money into this when I could put it in an index fund?"

WHAT MAKES YOU GO OUT:
- No revenue and no clear path to revenue
- Founders who are "in love" with their product but ignore the business
- Unrealistic valuations
- Products in crowded markets with no differentiation
- When founders reject royalty structures without good reason

SPEECH STYLE: Cold, calculating, uses money analogies. Often refers to money needing to "work for you." Use phrases like "Here's what I'll do..." or "Let me make you an offer..." Be blunt and sometimes harsh. Keep responses to 2-3 sentences.

IMPORTANT: Speak naturally as dialogue only. NEVER use roleplay actions like *crosses arms* or *shakes head*. Just speak your lines directly.""",

    'elena': """You are Lori Greiner, known as the "Queen of QVC." You've launched over 700 products and have unparalleled connections in the retail and home shopping world.

PERSONALITY:
- Warm but decisive - you know within seconds if a product is a "hero or a zero"
- Product-focused - you care about the physical product, packaging, and presentation
- Empathetic to founders but business-minded
- Gets excited about products that solve everyday problems
- Values products you can sell on TV and in stores

INVESTMENT STYLE:
- Prefers products over services or software
- Looks for products with broad consumer appeal
- Offers retail expertise as key value-add
- Often wants exclusivity in retail channels

TYPICAL QUESTIONS:
- "Is this patented?"
- "What's your cost to make it and what do you sell it for?"
- "Have you sold this in stores yet?"
- "What's the packaging like?"
- "Have you done any TV shopping before?"

WHAT MAKES YOU GO OUT:
- Products that don't solve a real problem
- Products that can't be demonstrated effectively
- Categories you don't understand or can't sell
- Founders who seem difficult to work with
- Products without patent protection in competitive spaces

SPEECH STYLE: Warm, enthusiastic about good products, maternal but firm. Use phrases like "I love this!" or "This is a hero!" when excited, or "I just don't see it" when passing. Keep responses to 2-3 sentences.

IMPORTANT: Speak naturally as dialogue only. NEVER use roleplay actions like *crosses arms* or *shakes head*. Just speak your lines directly.""",

    'richard': """You are Richard Branson, the legendary founder of Virgin Group with over 400 companies spanning airlines, music, telecommunications, and space travel. You're known for your adventurous spirit and unconventional approach.

PERSONALITY:
- Adventurous and willing to take calculated risks
- Focuses heavily on brand and customer experience
- Values disruption of established industries
- Charismatic and encouraging to founders
- Looks for the "fun factor" in businesses
- Believes in treating employees and customers well

INVESTMENT STYLE:
- Attracted to brand-building opportunities
- Looks for businesses that can become lifestyle brands
- Interested in disrupting traditional industries
- Values experiences over just products

TYPICAL QUESTIONS:
- "What's the customer experience like from start to finish?"
- "How does this disrupt the way things are currently done?"
- "What's the story behind the brand?"
- "How do you treat your team?"
- "Is this something I'd want to use myself?"

WHAT MAKES YOU GO OUT:
- Boring, commodity businesses
- Founders who don't seem passionate
- Poor customer experience design
- Businesses that exploit rather than help people
- Overly corporate, soulless pitches

SPEECH STYLE: Warm, storytelling-oriented, uses adventure metaphors. Often starts with "You know, I've always believed..." or shares relevant anecdotes. Be encouraging even when declining. Keep responses to 2-3 sentences.

IMPORTANT: Speak naturally as dialogue only. NEVER use roleplay actions like *crosses arms* or *shakes head*. Just speak your lines directly.""",

    'daniel': """You are Robert Herjavec, a tech entrepreneur who built The Herjavec Group into a leading cybersecurity firm. You're known for your encouraging demeanor and genuine desire to see entrepreneurs succeed.

PERSONALITY:
- Encouraging and supportive, but still shrewd
- Technical background - understands software and security deeply
- Appreciates hard work and hustle (self-made background)
- Gets emotional about founders' personal journeys
- Balanced between heart and business sense
- Will fight for deals you believe in

INVESTMENT STYLE:
- Prefers technology companies, especially cybersecurity
- Looks for recurring revenue models (SaaS)
- Values technical founders who understand their product
- Willing to mentor and provide hands-on help

TYPICAL QUESTIONS:
- "Tell me about your background - how did you get here?"
- "What's the technology behind this?"
- "Is this recurring revenue or one-time sales?"
- "What keeps you up at night about this business?"
- "Who's on your team?"

WHAT MAKES YOU GO OUT:
- Products that could pose security risks
- Founders who seem dishonest or evasive
- Businesses where you can't add value
- Unrealistic technical claims
- When another shark clearly wants it more

SPEECH STYLE: Empathetic, often connects personally with founders. Use phrases like "I really like you..." or "I believe in what you're doing, but..." When going out, often say "I'm going to step aside for my partners." Keep responses to 2-3 sentences.

IMPORTANT: Speak naturally as dialogue only. NEVER use roleplay actions like *crosses arms* or *shakes head*. Just speak your lines directly."""
}

# =============================================================================
# Confidence Modifiers
# =============================================================================

# Positive signals and their impact on each shark's confidence
POSITIVE_MODIFIERS = {
    'revenue': {'marcus': 15, 'victor': 25, 'elena': 10, 'richard': 5, 'daniel': 15},
    'patents': {'marcus': 20, 'victor': 10, 'elena': 25, 'richard': 5, 'daniel': 15},
    'users': {'marcus': 20, 'victor': 15, 'elena': 10, 'richard': 20, 'daniel': 20},
    'tech': {'marcus': 25, 'victor': 5, 'elena': 0, 'richard': 10, 'daniel': 30},
    'retail': {'marcus': 5, 'victor': 10, 'elena': 30, 'richard': 10, 'daniel': 5},
    'brand': {'marcus': 10, 'victor': 5, 'elena': 15, 'richard': 30, 'daniel': 10},
    'recurring': {'marcus': 20, 'victor': 20, 'elena': 10, 'richard': 15, 'daniel': 25},
    'growth': {'marcus': 20, 'victor': 15, 'elena': 15, 'richard': 20, 'daniel': 15},
}

# Negative signals
NEGATIVE_MODIFIERS = {
    'no_revenue': {'marcus': -15, 'victor': -30, 'elena': -20, 'richard': -10, 'daniel': -10},
    'no_protection': {'marcus': -20, 'victor': -10, 'elena': -25, 'richard': -5, 'daniel': -15},
    'crowded_market': {'marcus': -10, 'victor': -15, 'elena': -15, 'richard': -10, 'daniel': -20},
    'high_valuation': {'marcus': -15, 'victor': -25, 'elena': -20, 'richard': -10, 'daniel': -15},
}

# =============================================================================
# Confidence Thresholds for Flag System
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    'offer': 70,      # Shark will make offer when confidence >= this
    'out': 25,        # Shark will go out when confidence < this
    'recovery': 35,   # Clear "flagged for out" if confidence recovers above this
    'return': 70,     # Shark who went OUT can return if confidence >= this (very hard)
    'return_delta': 15  # Minimum confidence jump in one message to trigger return
}
POST_OFFER_SENSITIVITY = 0.5  # Confidence changes are multiplied by this after making offer

# =============================================================================
# Out Reasons by Shark
# =============================================================================

OUT_REASONS = {
    'marcus': [
        "I just don't see how this scales. I'm out.",
        "You don't know your numbers well enough. For that reason, I'm out.",
        "This isn't a technology play I can get behind. I'm out.",
        "The valuation just doesn't work for me. I'm out.",
        "I need to see more traction before I can invest. I'm out."
    ],
    'victor': [
        "There's no money here. I'm out.",
        "I can't make the numbers work. You're dead to me. I'm out.",
        "You're not offering me enough for my risk. I'm out.",
        "Without revenue, this is just a dream. I'm out.",
        "I don't see a path to profitability. I'm out."
    ],
    'elena': [
        "I don't think this is a retail product. I'm out.",
        "I just don't see it on the shelves. I'm out.",
        "This isn't my expertise, and I can't add value. I'm out.",
        "Without a patent, you're vulnerable. I'm out.",
        "I don't connect with this product. I'm out."
    ],
    'richard': [
        "I'm not feeling the passion here. I'm out.",
        "This doesn't excite me as a brand opportunity. I'm out.",
        "I can't see myself using this. I'm out.",
        "The customer experience isn't compelling. I'm out.",
        "I need to see more disruption. I'm out."
    ],
    'daniel': [
        "I'm going to step aside on this one. I'm out.",
        "I don't think I'm the right partner for you. I'm out.",
        "I wish you the best, but I can't add value here. I'm out.",
        "The tech doesn't convince me. I'm out.",
        "I'm going to let my partners fight for this one. I'm out."
    ]
}


# =============================================================================
# Investor Belief State - Tracks what each shark believes about the pitch
# =============================================================================

class InvestorBeliefState:
    """
    Tracks an investor's beliefs about a pitch to ensure consistency.
    Updated after pitch analysis and each dialogue turn.
    Integrates with ProofTracker and OfferProgression for validation.
    """

    def __init__(self, shark_id, pitch_data=None):
        self.shark_id = shark_id
        # Perceived stage: 'idea', 'mvp', 'traction', 'revenue', 'growth'
        self.perceived_stage = 'idea'
        # Key risks identified by this investor
        self.key_risks = []
        # What proof they need before investing (legacy - use proof_tracker)
        self.required_proof = []
        # How likely they are to invest: 'low', 'medium', 'high'
        self.capital_conviction = 'low'
        # Concerns they've explicitly stated
        self.stated_concerns = []
        # Positives they've explicitly stated
        self.stated_positives = []
        # Implied valuation range based on statements (min, max)
        self.implied_valuation_range = (0, 0)
        # Track what questions they've asked
        self.questions_asked = []
        # Track action types for consistency
        self.action_history = []

        # NEW: Integrated proof tracking
        self.proof_tracker = ProofTracker()
        # NEW: Offer progression tracking
        self.offer_progression = None  # Initialized with pitch_data
        # NEW: Negotiation willingness (decreases with rejections)
        self.negotiation_willingness = 1.0
        # NEW: Track competing offers seen
        self.competing_offers_seen = []
        # NEW: Last offer made by this shark
        self.last_offer = None
        # NEW: Initial ask valuation for reference
        self.initial_ask_valuation = 0

        if pitch_data:
            self._initialize_from_pitch(pitch_data)

    def _initialize_from_pitch(self, pitch_data):
        """Set initial belief state based on pitch data."""
        proof_type = pitch_data.get('proofType', 'idea')
        proof_value = pitch_data.get('proofValue', '')

        # Map proof type to perceived stage
        stage_map = {
            'idea': 'idea',
            'prototype': 'mvp',
            'users': 'traction',
            'customers': 'traction',
            'revenue': 'revenue'
        }
        self.perceived_stage = stage_map.get(proof_type, 'idea')

        # Calculate implied valuation from ask
        amount = pitch_data.get('amountRaising', 100000)
        equity = pitch_data.get('equityPercent', 10)
        if equity > 0:
            implied_val = amount / (equity / 100)
        else:
            implied_val = amount * 10

        self.initial_ask_valuation = implied_val

        # Set valuation range based on archetype tolerance
        archetype = INVESTOR_ARCHETYPES.get(self.shark_id, {})
        tolerance = archetype.get('valuation_tolerance', 'medium')

        if tolerance == 'low':
            self.implied_valuation_range = (implied_val * 0.3, implied_val * 0.8)
        elif tolerance == 'high':
            self.implied_valuation_range = (implied_val * 0.7, implied_val * 1.5)
        else:  # medium
            self.implied_valuation_range = (implied_val * 0.5, implied_val * 1.2)

        # Initialize offer progression with valuation bounds
        self.offer_progression = OfferProgression(self.shark_id, implied_val)
        self.offer_progression.set_valuation_bounds(
            floor_multiplier=0.3 if tolerance == 'low' else (0.5 if tolerance == 'medium' else 0.7),
            ceiling_multiplier=0.8 if tolerance == 'low' else (1.2 if tolerance == 'medium' else 1.5)
        )

        # Initialize conviction based on stage and archetype requirements
        archetype = INVESTOR_ARCHETYPES.get(self.shark_id, {})
        required = archetype.get('requires_for_equity')
        min_stage = archetype.get('min_stage_for_cash_equity', 'idea')

        current_stage_idx = STAGE_HIERARCHY.index(self.perceived_stage) if self.perceived_stage in STAGE_HIERARCHY else 0
        min_stage_idx = STAGE_HIERARCHY.index(min_stage) if min_stage in STAGE_HIERARCHY else 0

        if current_stage_idx >= min_stage_idx:
            self.capital_conviction = 'medium' if self.perceived_stage in ['traction', 'revenue', 'growth'] else 'low'
        else:
            self.capital_conviction = 'low'
            if required:
                self.required_proof.append(f"Need to see {required}")
                # Also add to proof tracker
                self.proof_tracker.require_proof(required, reason=f"Required for equity deal")

        # If proof was provided in pitch, satisfy it
        if proof_value and proof_type != 'idea':
            self._process_initial_proof(proof_type, proof_value)

    def add_concern(self, concern):
        """Record a stated concern."""
        if concern and concern not in self.stated_concerns:
            self.stated_concerns.append(concern)

    def add_positive(self, positive):
        """Record a stated positive."""
        if positive and positive not in self.stated_positives:
            self.stated_positives.append(positive)

    def add_required_proof(self, proof):
        """Record something they need to see."""
        if proof and proof not in self.required_proof:
            self.required_proof.append(proof)

    def add_risk(self, risk):
        """Record an identified risk."""
        if risk and risk not in self.key_risks:
            self.key_risks.append(risk)

    def record_action(self, action_type):
        """Record an action for history tracking."""
        self.action_history.append(action_type)

    def update_conviction(self, new_level):
        """Update capital conviction level."""
        if new_level in ['low', 'medium', 'high']:
            self.capital_conviction = new_level

    def upgrade_stage(self, new_stage):
        """Upgrade perceived stage if new info suggests higher."""
        if new_stage in STAGE_HIERARCHY:
            current_idx = STAGE_HIERARCHY.index(self.perceived_stage)
            new_idx = STAGE_HIERARCHY.index(new_stage)
            if new_idx > current_idx:
                self.perceived_stage = new_stage

    def can_make_unconditional_offer(self):
        """Check if this investor can make an unconditional cash offer."""
        # Check proof tracker first (preferred method)
        if not self.proof_tracker.can_make_unconditional_offer():
            return False
        # Legacy check - cannot if they've stated required proof
        if self.required_proof:
            return False
        # Cannot if conviction is still low
        if self.capital_conviction == 'low':
            return False
        return True

    def _process_initial_proof(self, proof_type, proof_value):
        """Process proof provided in the initial pitch."""
        proof_map = {
            'revenue': 'revenue',
            'users': 'users',
            'customers': 'users',
            'prototype': 'product'
        }
        mapped_type = proof_map.get(proof_type)
        if mapped_type:
            try:
                value = float(proof_value) if proof_value else 0
            except (ValueError, TypeError):
                value = True
            self.proof_tracker.satisfy_proof(mapped_type, value)

    def process_founder_message(self, message):
        """
        Process founder message for proofs and update state accordingly.
        Returns list of proofs found and whether any improved the state.
        """
        proofs_found = self.proof_tracker.check_message_for_proofs(message)

        valuation_multiplier = 1.0
        improvements = []

        for proof_type, value in proofs_found:
            satisfied, reason = self.proof_tracker.satisfy_proof(proof_type, value)
            if satisfied:
                improvements.append({
                    'type': proof_type,
                    'value': value,
                    'reason': reason
                })
                # Boost valuation range for satisfied proofs
                valuation_multiplier *= 1.10  # 10% boost per proof

                # Clear related concerns
                self._clear_related_concerns(proof_type)

                # Upgrade stage if appropriate
                stage_map = {
                    'revenue': 'revenue',
                    'users': 'traction',
                    'product': 'mvp',
                    'traction': 'traction'
                }
                if proof_type in stage_map:
                    self.upgrade_stage(stage_map[proof_type])

        # Update valuation range if improvements found
        if valuation_multiplier > 1.0:
            min_val, max_val = self.implied_valuation_range
            self.implied_valuation_range = (
                min_val * valuation_multiplier,
                max_val * valuation_multiplier
            )

            # Also update conviction if proofs were satisfied
            if self.capital_conviction == 'low':
                self.capital_conviction = 'medium'
            elif self.capital_conviction == 'medium' and len(improvements) > 1:
                self.capital_conviction = 'high'

        return {
            'proofs_found': proofs_found,
            'improvements': improvements,
            'valuation_boost': valuation_multiplier
        }

    def _clear_related_concerns(self, proof_type):
        """Remove concerns that are addressed by the proof."""
        concern_map = {
            'revenue': ['no revenue', 'pre-revenue', 'sales', 'money', 'profitable'],
            'users': ['no users', 'traction', 'customers', 'adoption'],
            'patents': ['no protection', 'ip', 'defensibility', 'competitor'],
            'team': ['experience', 'background', 'capability'],
            'product': ['prototype', 'mvp', 'working', 'built']
        }

        keywords = concern_map.get(proof_type, [])
        original_count = len(self.stated_concerns)
        self.stated_concerns = [
            c for c in self.stated_concerns
            if not any(kw in c.lower() for kw in keywords)
        ]

        # Also clear from required_proof
        self.required_proof = [
            p for p in self.required_proof
            if not any(kw in p.lower() for kw in keywords)
        ]

        return original_count - len(self.stated_concerns)

    def calculate_offer_terms(self, pitch_data, confidence):
        """
        Calculate offer terms respecting belief state, offer history, and valuation bounds.
        Returns dict with amount, equity, implied_valuation.
        """
        ask_amount = pitch_data.get('amountRaising', 100000)

        # Get constraints from offer progression
        if self.offer_progression:
            constraints = self.offer_progression.get_next_offer_constraints()
        else:
            constraints = {
                'min_valuation': self.implied_valuation_range[0],
                'max_valuation': self.implied_valuation_range[1],
                'suggested_valuation': sum(self.implied_valuation_range) / 2
            }

        # Determine target valuation based on conviction
        min_val, max_val = self.implied_valuation_range

        # Clamp to offer progression constraints if improving
        if constraints.get('must_improve') and 'last_valuation' in constraints:
            min_val = max(min_val, constraints['last_valuation'] * 1.02)

        # Higher conviction = closer to max valuation
        if self.capital_conviction == 'high':
            target_val = max_val * 0.90
        elif self.capital_conviction == 'medium':
            target_val = (min_val + max_val) / 2
        else:
            target_val = min_val * 1.10

        # Clamp target to bounds
        target_val = max(min_val, min(target_val, constraints.get('max_valuation', max_val)))

        # Apply negotiation willingness
        target_val = target_val * self.negotiation_willingness

        # Calculate equity from valuation
        equity = (ask_amount / target_val) * 100 if target_val > 0 else 50
        equity = round(min(equity, 50), 1)  # Cap at 50%

        return {
            'amount': ask_amount,
            'equity': equity,
            'implied_valuation': int(target_val),
            'conviction': self.capital_conviction,
            'constraints_used': constraints
        }

    def record_offer_made(self, offer):
        """Record that this shark made an offer."""
        self.last_offer = offer
        if self.offer_progression:
            self.offer_progression.record_offer(offer)

    def record_rejection(self):
        """Record that founder rejected/declined our offer."""
        self.negotiation_willingness = max(0.5, self.negotiation_willingness - 0.1)
        if self.offer_progression:
            self.offer_progression.record_rejection()

    def record_counter(self):
        """Record that founder countered our offer."""
        if self.offer_progression:
            self.offer_progression.record_counter()

    def see_competing_offer(self, offer):
        """Record seeing a competing offer from another shark."""
        self.competing_offers_seen.append({
            'shark_id': offer.get('sharkId'),
            'valuation': offer.get('implied_valuation', 0),
            'timestamp': time.time()
        })

    def get_best_competing_valuation(self):
        """Get the highest competing valuation seen."""
        if not self.competing_offers_seen:
            return 0
        return max(o['valuation'] for o in self.competing_offers_seen)

    def should_beat_competitor(self):
        """Determine if we should try to beat competing offers."""
        if not self.competing_offers_seen:
            return False, 0

        best_competing = self.get_best_competing_valuation()
        our_best = self.last_offer.get('implied_valuation', 0) if self.last_offer else 0

        # Only beat if we're highly convicted and they're offering more
        if self.capital_conviction == 'high' and best_competing > our_best:
            # Beat by 5%
            return True, best_competing * 1.05

        return False, 0

    def get_appropriate_deal_types(self):
        """Get deal types this investor can use given their belief state."""
        archetype = INVESTOR_ARCHETYPES.get(self.shark_id, {})
        allowed = archetype.get('allowed_deals', ['cash_equity'])

        appropriate = []
        for deal_type in allowed:
            # cash_equity requires meeting stage requirements
            if deal_type == 'cash_equity':
                min_stage = archetype.get('min_stage_for_cash_equity', 'idea')
                current_idx = STAGE_HIERARCHY.index(self.perceived_stage) if self.perceived_stage in STAGE_HIERARCHY else 0
                min_idx = STAGE_HIERARCHY.index(min_stage) if min_stage in STAGE_HIERARCHY else 0
                if current_idx >= min_idx and self.capital_conviction != 'low':
                    appropriate.append(deal_type)
            # SAFE/milestone deals are for lower conviction
            elif deal_type in ['safe_cap', 'safe_milestone', 'tranche']:
                appropriate.append(deal_type)
            # Royalty always available if allowed
            elif deal_type == 'royalty':
                appropriate.append(deal_type)

        return appropriate if appropriate else ['no_offer']

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'shark_id': self.shark_id,
            'perceived_stage': self.perceived_stage,
            'key_risks': self.key_risks,
            'required_proof': self.required_proof,
            'capital_conviction': self.capital_conviction,
            'stated_concerns': self.stated_concerns,
            'stated_positives': self.stated_positives,
            'implied_valuation_range': list(self.implied_valuation_range),
            'questions_asked': self.questions_asked,
            'action_history': self.action_history,
            # New fields
            'proof_tracker': self.proof_tracker.to_dict() if self.proof_tracker else None,
            'offer_progression': self.offer_progression.to_dict() if self.offer_progression else None,
            'negotiation_willingness': self.negotiation_willingness,
            'competing_offers_seen': self.competing_offers_seen,
            'last_offer': self.last_offer,
            'initial_ask_valuation': self.initial_ask_valuation
        }

    @classmethod
    def from_dict(cls, data):
        """Reconstruct from dictionary."""
        state = cls(data.get('shark_id', 'marcus'))
        state.perceived_stage = data.get('perceived_stage', 'idea')
        state.key_risks = data.get('key_risks', [])
        state.required_proof = data.get('required_proof', [])
        state.capital_conviction = data.get('capital_conviction', 'low')
        state.stated_concerns = data.get('stated_concerns', [])
        state.stated_positives = data.get('stated_positives', [])
        state.implied_valuation_range = tuple(data.get('implied_valuation_range', [0, 0]))
        state.questions_asked = data.get('questions_asked', [])
        state.action_history = data.get('action_history', [])
        # New fields
        if data.get('proof_tracker'):
            state.proof_tracker = ProofTracker.from_dict(data['proof_tracker'])
        if data.get('offer_progression'):
            state.offer_progression = OfferProgression.from_dict(data['offer_progression'])
        state.negotiation_willingness = data.get('negotiation_willingness', 1.0)
        state.competing_offers_seen = data.get('competing_offers_seen', [])
        state.last_offer = data.get('last_offer')
        state.initial_ask_valuation = data.get('initial_ask_valuation', 0)
        return state


class SharkManager:
    """Manages shark personas, confidence, and decision logic."""

    def get_shark_name(self, shark_id):
        """Get the display name for a shark."""
        return SHARK_NAMES.get(shark_id, shark_id)

    def get_persona(self, shark_id):
        """Get the full persona prompt for a shark."""
        return SHARK_PERSONAS.get(shark_id, '')

    def calculate_initial_confidence(self, shark_id, pitch_data):
        """Calculate initial confidence based on pitch data."""
        base = 50

        # Valuation check
        amount = pitch_data.get('amountRaising', 0)
        equity = pitch_data.get('equityPercent', 10)
        if equity > 0:
            valuation = amount / (equity / 100)
        else:
            valuation = amount * 10

        proof_type = pitch_data.get('proofType', 'idea')
        proof_value = pitch_data.get('proofValue', '')

        # High valuation with no traction
        if valuation > 5000000 and proof_type == 'idea':
            base += NEGATIVE_MODIFIERS['high_valuation'].get(shark_id, -15)

        # Proof type bonuses
        if proof_type == 'revenue':
            base += POSITIVE_MODIFIERS['revenue'].get(shark_id, 10)
            # Extra bonus for high revenue
            try:
                revenue = int(proof_value) if proof_value else 0
                if revenue > 100000:
                    base += 10
                if revenue > 500000:
                    base += 10
            except (ValueError, TypeError):
                pass

        elif proof_type == 'users':
            base += POSITIVE_MODIFIERS['users'].get(shark_id, 10)

        elif proof_type == 'customers':
            base += POSITIVE_MODIFIERS['revenue'].get(shark_id, 5)

        elif proof_type == 'idea':
            base += NEGATIVE_MODIFIERS['no_revenue'].get(shark_id, -15)

        # Description analysis
        desc = (pitch_data.get('companyDescription', '') + ' ' +
                pitch_data.get('whyNow', '')).lower()

        # Tech keywords
        if any(word in desc for word in ['software', 'app', 'platform', 'saas', 'ai', 'tech', 'algorithm']):
            base += POSITIVE_MODIFIERS['tech'].get(shark_id, 10)

        # Retail keywords
        if any(word in desc for word in ['retail', 'store', 'consumer', 'product', 'packaging', 'shelf']):
            base += POSITIVE_MODIFIERS['retail'].get(shark_id, 10)

        # Brand keywords
        if any(word in desc for word in ['brand', 'experience', 'lifestyle', 'community']):
            base += POSITIVE_MODIFIERS['brand'].get(shark_id, 10)

        # Recurring revenue keywords
        if any(word in desc for word in ['subscription', 'recurring', 'monthly', 'saas', 'mrr']):
            base += POSITIVE_MODIFIERS['recurring'].get(shark_id, 10)

        # Patent mention
        if 'patent' in desc:
            base += POSITIVE_MODIFIERS['patents'].get(shark_id, 10)

        return max(0, min(100, base))

    def update_confidence_from_transcript(self, shark_id, transcript, current_confidence):
        """Update confidence based on pitch transcript content."""
        if not transcript:
            return current_confidence

        # Combine all transcript text
        text = ' '.join([t.get('text', '') for t in transcript]).lower()
        delta = 0

        # Positive signals
        if 'patent' in text or 'patented' in text or 'intellectual property' in text:
            delta += POSITIVE_MODIFIERS['patents'].get(shark_id, 10) // 2

        if 'million' in text and ('revenue' in text or 'sales' in text):
            delta += POSITIVE_MODIFIERS['revenue'].get(shark_id, 15)

        if 'growing' in text or 'growth' in text or 'doubled' in text:
            delta += POSITIVE_MODIFIERS['growth'].get(shark_id, 10) // 2

        if 'recurring' in text or 'subscription' in text or 'monthly' in text:
            delta += POSITIVE_MODIFIERS['recurring'].get(shark_id, 10) // 2

        # Negative signals
        if 'no revenue' in text or "haven't sold" in text or 'pre-revenue' in text:
            delta += NEGATIVE_MODIFIERS['no_revenue'].get(shark_id, -15) // 2

        if 'no patent' in text or 'not patented' in text:
            delta += NEGATIVE_MODIFIERS['no_protection'].get(shark_id, -10) // 2

        if 'competitive' in text or 'crowded' in text or 'many competitors' in text:
            delta += NEGATIVE_MODIFIERS['crowded_market'].get(shark_id, -10) // 2

        return max(0, min(100, current_confidence + delta))

    def should_go_out(self, shark_id, confidence, phase, context, shark_state=None):
        """
        Determine if shark should go out on their speaking turn.
        Now checks the flagged_for_out flag instead of immediate confidence check.
        """
        if phase == 'pitch':
            return False

        # If shark_state provided, check flag
        if shark_state:
            if not shark_state.get('flagged_for_out', False):
                return False

            # Verify confidence is still below recovery threshold
            if confidence >= CONFIDENCE_THRESHOLDS['recovery']:
                return False

        else:
            # Fallback to old logic if no state provided
            if confidence >= CONFIDENCE_THRESHOLDS['out']:
                return False

        # Must have asked at least 1 question before going out
        question_count = context.get('questionCount', 0)
        if question_count < 1:
            return False

        return True

    def get_out_reason(self, shark_id):
        """Get a contextual reason for going out."""
        reasons = OUT_REASONS.get(shark_id, ["I'm out."])
        return random.choice(reasons)

    def should_make_offer(self, shark_id, confidence, phase, context, shark_state=None):
        """
        Determine if shark should make an offer on their speaking turn.
        Now checks the flagged_for_offer flag.
        """
        if phase not in ['qa', 'offers']:
            return False

        # If shark_state provided, check flag
        if shark_state:
            if not shark_state.get('flagged_for_offer', False):
                return False

            # Verify confidence is still above threshold
            if confidence < CONFIDENCE_THRESHOLDS['offer']:
                return False
        else:
            # Fallback to old logic if no state provided
            if confidence < CONFIDENCE_THRESHOLDS['offer']:
                return False

        return True

    # =========================================================================
    # Confidence Flag System - New Methods
    # =========================================================================

    def evaluate_confidence_flags(self, shark_id, confidence, shark_state):
        """
        Evaluate confidence and set appropriate flags.
        Does NOT immediately trigger offer/out - just sets flags.
        Returns updated flag states.
        """
        current_has_offered = shark_state.get('has_made_offer', False)
        current_flagged_for_out = shark_state.get('flagged_for_out', False)

        flags = {
            'flagged_for_offer': False,
            'flagged_for_out': current_flagged_for_out  # Preserve existing out flag
        }

        # Flag for offer if confidence is high enough
        # Only flag if hasn't offered yet OR confidence is very high (re-offer opportunity)
        if confidence >= CONFIDENCE_THRESHOLDS['offer']:
            if not current_has_offered or confidence >= 85:
                flags['flagged_for_offer'] = True

        # Flag for out if confidence is low
        if confidence < CONFIDENCE_THRESHOLDS['out']:
            flags['flagged_for_out'] = True
        # Clear out flag if confidence recovered
        elif confidence >= CONFIDENCE_THRESHOLDS['recovery']:
            flags['flagged_for_out'] = False

        return flags

    def calculate_confidence_delta_from_message(self, shark_id, message, shark_state):
        """
        Calculate confidence change based on user's message content.
        This is called for EVERY shark after user message.
        """
        text = message.lower()
        delta = 0

        # Positive signals
        if 'patent' in text or 'patented' in text:
            delta += POSITIVE_MODIFIERS['patents'].get(shark_id, 10) // 3

        if any(word in text for word in ['revenue', 'sales', 'profit', 'making money']):
            delta += POSITIVE_MODIFIERS['revenue'].get(shark_id, 10) // 3
            # Extra for numbers mentioned
            if any(word in text for word in ['million', 'thousand', '100k', '500k', '1m']):
                delta += 5

        if any(word in text for word in ['users', 'customers', 'subscribers', 'downloads']):
            delta += POSITIVE_MODIFIERS['users'].get(shark_id, 10) // 3

        if any(word in text for word in ['growing', 'growth', 'doubled', 'tripled', 'increasing']):
            delta += POSITIVE_MODIFIERS['growth'].get(shark_id, 10) // 3

        if any(word in text for word in ['recurring', 'subscription', 'saas', 'mrr', 'arr']):
            delta += POSITIVE_MODIFIERS['recurring'].get(shark_id, 10) // 3

        # Negative signals
        if any(phrase in text for phrase in ['no revenue', "haven't sold", 'pre-revenue', 'no sales', "don't have sales"]):
            delta += NEGATIVE_MODIFIERS['no_revenue'].get(shark_id, -10) // 3

        if any(phrase in text for phrase in ['no patent', 'not patented', 'no protection', "don't have a patent"]):
            delta += NEGATIVE_MODIFIERS['no_protection'].get(shark_id, -10) // 3

        if any(phrase in text for phrase in ['many competitors', 'crowded market', 'competitive space', 'lots of competition']):
            delta += NEGATIVE_MODIFIERS['crowded_market'].get(shark_id, -10) // 3

        # Evasive or weak answers
        if any(phrase in text for phrase in ["don't know", "not sure", "haven't figured", "working on that", "i think", "maybe"]):
            delta -= 5

        # Strong answers
        if any(phrase in text for phrase in ['absolutely', 'definitely', 'proven', 'validated', 'confirmed']):
            delta += 3

        return delta

    def calculate_all_sharks_confidence_update(self, session_sharks, user_message):
        """
        Update confidence for ALL sharks based on user message.
        Returns dict of {shark_id: {new_confidence, delta, flags, should_return}}.
        """
        results = {}

        for shark_id, shark_data in session_sharks.items():
            current_status = shark_data.get('status', 'live')
            current_confidence = shark_data.get('confidence', 50)
            sensitivity = shark_data.get('post_offer_sensitivity', 1.0)

            # Calculate delta from message analysis
            raw_delta = self.calculate_confidence_delta_from_message(
                shark_id, user_message, shark_data
            )

            # Apply sensitivity modifier
            adjusted_delta = int(raw_delta * sensitivity)

            # Calculate new confidence
            new_confidence = max(0, min(100, current_confidence + adjusted_delta))

            # Check if OUT shark can return (requires high confidence AND big delta)
            should_return = False
            if current_status == 'out':
                should_return = self.check_shark_return(shark_id, new_confidence, adjusted_delta, shark_data)

            # Evaluate flags (only for live sharks or returning sharks)
            if current_status == 'live' or should_return:
                flags = self.evaluate_confidence_flags(shark_id, new_confidence, shark_data)
            else:
                flags = {'flagged_for_offer': False, 'flagged_for_out': False}

            results[shark_id] = {
                'new_confidence': new_confidence,
                'delta': adjusted_delta,
                'raw_delta': raw_delta,
                'flags': flags,
                'should_return': should_return
            }

        return results

    def check_shark_return(self, shark_id, confidence, delta, shark_state):
        """
        Check if a shark who went OUT can return to the deal.
        Returns True if shark should come back.

        Requires BOTH:
        - Confidence >= 70 (return threshold)
        - Delta >= 15 in a single message (significant positive shift)
        """
        # Only check if shark is actually out
        if shark_state.get('status') != 'out':
            return False

        # Must have confidence above return threshold
        if confidence < CONFIDENCE_THRESHOLDS['return']:
            return False

        # Must have a significant positive delta in this message
        if delta < CONFIDENCE_THRESHOLDS.get('return_delta', 15):
            return False

        return True

    def get_return_message(self, shark_id):
        """Get a message for when a shark returns to the deal."""
        return_messages = {
            'marcus': "Hold on, I heard something that changed my mind. I'm back in.",
            'victor': "Wait a minute. Those numbers just got interesting. I'm listening again.",
            'elena': "You know what? I want to hear more. I'm back.",
            'richard': "That's the kind of thing I love to hear. Count me back in.",
            'daniel': "I'm sorry I stepped away. Let me reconsider this."
        }
        return return_messages.get(shark_id, "I'm back in the deal.")

    def generate_offer_terms(self, shark_id, pitch_data, confidence):
        """Generate offer terms based on shark personality."""
        ask_amount = pitch_data.get('amountRaising', 100000)
        ask_equity = pitch_data.get('equityPercent', 10)

        offer = {
            'sharkId': shark_id,
            'sharkName': self.get_shark_name(shark_id),
            'amount': ask_amount,
            'equity': ask_equity,
            'royalty': None,
            'royaltyUntil': None,
            'conditions': []
        }

        # Victor always tries royalty
        if shark_id == 'victor':
            offer['royalty'] = round(random.uniform(1.5, 3.5), 2)
            offer['royaltyUntil'] = ask_amount
            offer['equity'] = max(ask_equity - 5, 5)

        # Marcus often asks for more equity
        elif shark_id == 'marcus':
            if confidence > 85:
                offer['equity'] = ask_equity
            else:
                offer['equity'] = min(ask_equity + random.randint(5, 15), 50)

        # Elena wants retail exclusivity
        elif shark_id == 'elena':
            offer['conditions'].append('Exclusive retail/QVC rights')
            offer['equity'] = ask_equity + random.randint(3, 8)

        # Richard is usually fair
        elif shark_id == 'richard':
            if confidence > 80:
                offer['equity'] = ask_equity
            else:
                offer['equity'] = ask_equity + random.randint(2, 7)

        # Daniel is encouraging but business-minded
        elif shark_id == 'daniel':
            offer['equity'] = ask_equity + random.randint(0, 10)
            if confidence > 80:
                offer['conditions'].append('Mentorship and tech advisory')

        # Lower confidence = worse terms
        if confidence < 70:
            offer['equity'] = min(offer['equity'] + 10, 50)

        return offer

    def parse_offer_from_response(self, shark_id, response, pitch_data, confidence=70):
        """
        Detect if response contains an offer and generate consistent terms.

        Instead of parsing exact values from AI text (which can be inconsistent),
        we detect offer intent and use generate_offer_terms for the actual values.
        This ensures the offer card matches what the shark "meant" to offer.
        """
        response_lower = response.lower()

        # Check if this looks like an offer
        offer_indicators = ['offer', "i'll give you", 'deal:', 'here\'s what i\'ll do',
                           'i\'m in for', 'investment of', "here's my offer",
                           "i'll do", "let me make you"]

        if not any(ind in response_lower for ind in offer_indicators):
            return None

        # Also make sure they're not going out in the same breath
        out_indicators = ["i'm out", "im out", "i am out", "count me out"]
        if any(ind in response_lower for ind in out_indicators):
            return None

        # Offer detected - generate consistent terms based on shark personality
        # This ensures the offer card values are predictable and match shark behavior
        offer = self.generate_offer_terms(shark_id, pitch_data, confidence)

        # Add unique ID for offer tracking
        import uuid
        offer['id'] = str(uuid.uuid4())[:8]

        return offer

    def validate_offer_consistency(self, shark_id, belief_state, proposed_offer):
        """
        Validates that an offer is consistent with the investor's belief state.
        Returns (is_valid, reason) tuple.
        """
        archetype = INVESTOR_ARCHETYPES.get(shark_id, {})

        # Check 1: Deal type is allowed for this archetype
        deal_type = proposed_offer.get('deal_type', 'cash_equity')
        if deal_type in archetype.get('disallowed_deals', []):
            return False, f"Deal type '{deal_type}' not allowed for this investor"

        if deal_type not in archetype.get('allowed_deals', ['cash_equity']):
            return False, f"Deal type '{deal_type}' not in investor's repertoire"

        # Check 2: Stage requirements for cash equity
        if deal_type == 'cash_equity':
            min_stage = archetype.get('min_stage_for_cash_equity', 'idea')
            perceived_stage = belief_state.perceived_stage if hasattr(belief_state, 'perceived_stage') else belief_state.get('perceived_stage', 'idea')
            current_idx = STAGE_HIERARCHY.index(perceived_stage) if perceived_stage in STAGE_HIERARCHY else 0
            min_idx = STAGE_HIERARCHY.index(min_stage) if min_stage in STAGE_HIERARCHY else 0

            if current_idx < min_idx:
                return False, f"Investor requires {min_stage} stage for cash equity deals"

        # Check 3: Valuation consistency
        implied_val = proposed_offer.get('implied_valuation', 0)
        if implied_val > 0:
            val_range = belief_state.implied_valuation_range if hasattr(belief_state, 'implied_valuation_range') else belief_state.get('implied_valuation_range', (0, float('inf')))
            min_val, max_val = val_range
            # Allow some flexibility but not wild swings
            if implied_val < min_val * 0.5:
                return False, "Implied valuation too low vs stated beliefs"
            if implied_val > max_val * 2:
                return False, "Implied valuation too high vs stated beliefs"

        # Check 4: Cannot make unconditional offer if proof required
        required_proof = belief_state.required_proof if hasattr(belief_state, 'required_proof') else belief_state.get('required_proof', [])
        conditions = proposed_offer.get('conditions', [])
        if required_proof and not conditions and deal_type == 'cash_equity':
            return False, "Investor stated proof required but offer has no conditions"

        # Check 5: Cannot contradict stated concerns
        stated_concerns = belief_state.stated_concerns if hasattr(belief_state, 'stated_concerns') else belief_state.get('stated_concerns', [])
        if stated_concerns and deal_type == 'cash_equity':
            conviction = belief_state.capital_conviction if hasattr(belief_state, 'capital_conviction') else belief_state.get('capital_conviction', 'low')
            if conviction == 'low':
                return False, "Capital conviction too low for unconditional offer"

        return True, None

    def generate_structured_offer(self, shark_id, pitch_data, belief_state, confidence):
        """
        Generate an offer with full deal structure based on belief state.
        Returns offer dict with deal_type, terms, conditions, rationale, etc.
        """
        import uuid

        ask_amount = pitch_data.get('amountRaising', 100000)
        ask_equity = pitch_data.get('equityPercent', 10)
        implied_val_from_ask = ask_amount / (ask_equity / 100) if ask_equity > 0 else ask_amount * 10

        archetype = INVESTOR_ARCHETYPES.get(shark_id, {})

        # Determine appropriate deal type based on belief state
        appropriate_types = belief_state.get_appropriate_deal_types() if hasattr(belief_state, 'get_appropriate_deal_types') else ['cash_equity']

        # Select best deal type
        deal_type = self._select_deal_type(shark_id, appropriate_types, belief_state, confidence)

        # Build offer based on deal type
        offer = {
            'id': str(uuid.uuid4())[:8],
            'sharkId': shark_id,
            'sharkName': self.get_shark_name(shark_id),
            'deal_type': deal_type,
            'terms': {},
            'conditions': [],
            'implied_valuation': 0,
            'rationale': '',
            'belief_state_snapshot': belief_state.to_dict() if hasattr(belief_state, 'to_dict') else belief_state
        }

        # Generate terms based on deal type
        if deal_type == 'cash_equity':
            offer = self._generate_cash_equity_terms(offer, shark_id, ask_amount, ask_equity, confidence)

        elif deal_type == 'royalty':
            offer = self._generate_royalty_terms(offer, shark_id, ask_amount, ask_equity, confidence)

        elif deal_type == 'safe_cap':
            offer = self._generate_safe_cap_terms(offer, shark_id, ask_amount, implied_val_from_ask, confidence)

        elif deal_type == 'safe_milestone':
            offer = self._generate_safe_milestone_terms(offer, shark_id, ask_amount, implied_val_from_ask, belief_state, confidence)

        elif deal_type == 'tranche':
            offer = self._generate_tranche_terms(offer, shark_id, ask_amount, ask_equity, belief_state, confidence)

        else:  # no_offer
            offer = self._generate_no_offer_terms(offer, shark_id, belief_state)

        # Validate before returning
        is_valid, reason = self.validate_offer_consistency(shark_id, belief_state, offer)
        if not is_valid:
            # Fall back to a conditional offer if validation fails
            offer['deal_type'] = 'no_offer'
            offer['conditions'] = belief_state.required_proof if hasattr(belief_state, 'required_proof') else []
            offer['rationale'] = f"Cannot make direct offer: {reason}"

        # Add backwards-compatible fields
        offer['amount'] = offer['terms'].get('amount', ask_amount)
        offer['equity'] = offer['terms'].get('equity', ask_equity)
        offer['royalty'] = offer['terms'].get('royalty_percent')
        offer['royaltyUntil'] = offer['terms'].get('royalty_cap')

        return offer

    def _select_deal_type(self, shark_id, appropriate_types, belief_state, confidence):
        """Select the best deal type for this situation."""
        archetype = INVESTOR_ARCHETYPES.get(shark_id, {})

        # Victor strongly prefers royalty
        if shark_id == 'victor' and 'royalty' in appropriate_types:
            return 'royalty'

        # High confidence -> cash equity if allowed
        if confidence >= 75 and 'cash_equity' in appropriate_types:
            return 'cash_equity'

        # Daniel/Elena prefer milestone deals for uncertain situations
        if shark_id in ['daniel', 'elena'] and confidence < 70:
            if 'safe_milestone' in appropriate_types:
                return 'safe_milestone'
            if 'tranche' in appropriate_types:
                return 'tranche'

        # Marcus prefers SAFE for high-valuation tech
        if shark_id == 'marcus' and 'safe_cap' in appropriate_types:
            conviction = belief_state.capital_conviction if hasattr(belief_state, 'capital_conviction') else belief_state.get('capital_conviction', 'low')
            if conviction == 'medium':
                return 'safe_cap'

        # Default to first appropriate type
        return appropriate_types[0] if appropriate_types else 'no_offer'

    def _generate_cash_equity_terms(self, offer, shark_id, ask_amount, ask_equity, confidence):
        """Generate cash for equity offer terms."""
        # Shark-specific equity adjustments
        if shark_id == 'marcus':
            equity = ask_equity if confidence > 85 else min(ask_equity + random.randint(5, 15), 50)
        elif shark_id == 'richard':
            equity = ask_equity if confidence > 80 else ask_equity + random.randint(2, 7)
        elif shark_id == 'elena':
            equity = ask_equity + random.randint(3, 8)
            offer['conditions'].append('Exclusive retail/QVC rights')
        elif shark_id == 'daniel':
            equity = ask_equity + random.randint(0, 10)
            if confidence > 80:
                offer['conditions'].append('Mentorship and tech advisory')
        else:
            equity = ask_equity + random.randint(5, 10)

        # Lower confidence = worse terms
        if confidence < 70:
            equity = min(equity + 10, 50)

        offer['terms'] = {
            'amount': ask_amount,
            'equity': equity
        }
        offer['implied_valuation'] = int(ask_amount / (equity / 100)) if equity > 0 else ask_amount * 10
        offer['rationale'] = f"Direct investment at {equity}% equity"

        return offer

    def _generate_royalty_terms(self, offer, shark_id, ask_amount, ask_equity, confidence):
        """Generate royalty deal terms."""
        royalty_percent = round(random.uniform(1.5, 3.5), 2)
        royalty_cap = ask_amount * random.uniform(1.5, 2.5)
        equity = max(ask_equity - 5, 5)

        offer['terms'] = {
            'amount': ask_amount,
            'equity': equity,
            'royalty_percent': royalty_percent,
            'royalty_cap': int(royalty_cap)
        }
        offer['implied_valuation'] = int(ask_amount / (equity / 100)) if equity > 0 else ask_amount * 10
        offer['rationale'] = f"${royalty_percent}/unit royalty until ${int(royalty_cap)} recouped, plus {equity}% equity"

        return offer

    def _generate_safe_cap_terms(self, offer, shark_id, ask_amount, implied_val, confidence):
        """Generate SAFE with valuation cap terms."""
        # Cap at a discount to current ask valuation
        discount = 0.8 if confidence > 70 else 0.7
        valuation_cap = int(implied_val * discount)

        offer['terms'] = {
            'amount': ask_amount,
            'valuation_cap': valuation_cap
        }
        offer['implied_valuation'] = valuation_cap
        offer['rationale'] = f"SAFE note with ${valuation_cap:,} cap - converts at next priced round"

        return offer

    def _generate_safe_milestone_terms(self, offer, shark_id, ask_amount, implied_val, belief_state, confidence):
        """Generate SAFE with milestone trigger terms."""
        required_proof = belief_state.required_proof if hasattr(belief_state, 'required_proof') else belief_state.get('required_proof', [])

        # Define milestone based on what proof is needed
        if required_proof:
            milestone = required_proof[0]
        else:
            milestones = [
                "Achieve $100k in revenue",
                "Reach 10,000 active users",
                "Close 3 enterprise customers",
                "Launch MVP in market"
            ]
            milestone = random.choice(milestones)

        valuation_cap = int(implied_val * 0.75)

        offer['terms'] = {
            'amount': ask_amount,
            'valuation_cap': valuation_cap,
            'milestone': milestone
        }
        offer['conditions'] = [milestone]
        offer['implied_valuation'] = valuation_cap
        offer['rationale'] = f"SAFE converts when: {milestone}"

        return offer

    def _generate_tranche_terms(self, offer, shark_id, ask_amount, ask_equity, belief_state, confidence):
        """Generate tranche-based investment terms."""
        required_proof = belief_state.required_proof if hasattr(belief_state, 'required_proof') else belief_state.get('required_proof', [])

        # Split into 2-3 tranches
        tranche1_amount = int(ask_amount * 0.4)
        tranche2_amount = int(ask_amount * 0.35)
        tranche3_amount = ask_amount - tranche1_amount - tranche2_amount

        tranches = [
            {'amount': tranche1_amount, 'trigger': 'Upon signing', 'equity': int(ask_equity * 0.4)},
            {'amount': tranche2_amount, 'trigger': required_proof[0] if required_proof else 'Hit first milestone', 'equity': int(ask_equity * 0.35)},
            {'amount': tranche3_amount, 'trigger': 'Achieve growth targets', 'equity': ask_equity - int(ask_equity * 0.75)}
        ]

        offer['terms'] = {
            'total_amount': ask_amount,
            'tranches': tranches
        }
        offer['conditions'] = [t['trigger'] for t in tranches[1:]]
        offer['implied_valuation'] = int(ask_amount / (ask_equity / 100)) if ask_equity > 0 else ask_amount * 10
        offer['rationale'] = f"${tranche1_amount:,} now, rest upon milestones"

        return offer

    def _generate_no_offer_terms(self, offer, shark_id, belief_state):
        """Generate conditional no-offer with return conditions."""
        required_proof = belief_state.required_proof if hasattr(belief_state, 'required_proof') else belief_state.get('required_proof', [])
        stated_concerns = belief_state.stated_concerns if hasattr(belief_state, 'stated_concerns') else belief_state.get('stated_concerns', [])

        conditions = required_proof.copy() if required_proof else []
        if stated_concerns and not conditions:
            conditions = [f"Address: {concern}" for concern in stated_concerns[:2]]

        if not conditions:
            conditions = ["Come back with more traction"]

        offer['terms'] = {
            'conditions_to_return': conditions
        }
        offer['conditions'] = conditions
        offer['rationale'] = "Not ready to invest yet - come back when conditions met"

        return offer
