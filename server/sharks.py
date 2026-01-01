"""
Shark Personas and Logic for Shark Tank Simulator
Based on real Shark Tank investors
"""

import random
import re

# Shark IDs and mappings
SHARK_IDS = ['marcus', 'victor', 'elena', 'richard', 'daniel']

SHARK_NAMES = {
    'marcus': 'Marcus Kellan',
    'victor': 'Victor Slate',
    'elena': 'Elena Brooks',
    'richard': 'Richard Hale',
    'daniel': 'Daniel Frost'
}

SHARK_REAL_COUNTERPARTS = {
    'marcus': 'Mark Cuban',
    'victor': 'Kevin O\'Leary',
    'elena': 'Lori Greiner',
    'richard': 'Richard Branson',
    'daniel': 'Robert Herjavec'
}

# =============================================================================
# Shark Persona Prompts
# =============================================================================

SHARK_PERSONAS = {
    'marcus': """You are Marcus Kellan, a tech billionaire and owner of professional sports teams. You made your fortune in the tech industry and are known for your direct, no-nonsense approach.

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

    'victor': """You are Victor Slate, known as "Mr. Ruthless" in investment circles. You're a shrewd businessman who made your fortune in software and licensing deals.

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

    'elena': """You are Elena Brooks, known as the "Queen of Retail." You've launched hundreds of products and have unparalleled connections in the retail and home shopping world.

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

    'richard': """You are Richard Hale, a legendary entrepreneur known for building a global brand empire spanning airlines, music, and telecommunications. You're known for your adventurous spirit and unconventional approach.

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

    'daniel': """You are Daniel Frost, a tech entrepreneur who built a cybersecurity empire from nothing. You're known for your encouraging demeanor and genuine desire to see entrepreneurs succeed.

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

    def should_go_out(self, shark_id, confidence, phase, context):
        """Determine if shark should declare 'I'm out'."""
        # Never go out during pitch phase
        if phase == 'pitch':
            return False

        # Sharks should ask at least 2-3 questions before going out
        question_count = context.get('questionCount', 0)
        if question_count < 2:
            return False  # Always ask questions first!

        # Very low confidence after asking questions
        if confidence < 15 and question_count >= 2:
            return True

        # Low confidence after many interactions
        if question_count >= 4 and confidence < 30:
            return True

        # Shark-specific triggers (only after asking questions)
        if question_count >= 2:
            if shark_id == 'victor' and context.get('rejectedRoyalty'):
                return random.random() < 0.6  # 60% chance to leave

            if shark_id == 'marcus' and context.get('mentionedRoyalty'):
                return random.random() < 0.4  # 40% chance if royalty mentioned

        return False

    def get_out_reason(self, shark_id):
        """Get a contextual reason for going out."""
        reasons = OUT_REASONS.get(shark_id, ["I'm out."])
        return random.choice(reasons)

    def should_make_offer(self, shark_id, confidence, phase, context):
        """Determine if shark should make an offer."""
        if phase not in ['qa', 'offers']:
            return False

        if confidence < 60:
            return False

        # Higher confidence = higher chance
        if confidence > 85:
            return random.random() < 0.8
        if confidence > 75:
            return random.random() < 0.5
        if confidence > 65:
            return random.random() < 0.3

        return random.random() < 0.15

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

    def parse_offer_from_response(self, shark_id, response, pitch_data):
        """Try to extract offer terms from a shark's response."""
        response_lower = response.lower()

        # Check if this looks like an offer
        offer_indicators = ['offer', "i'll give you", 'deal:', 'here\'s what i\'ll do',
                           'i\'m in for', 'investment of']

        if not any(ind in response_lower for ind in offer_indicators):
            return None

        # Try to extract amount
        amount_match = re.search(r'\$?([\d,]+)\s*(?:thousand|k)?', response)
        amount = None
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            try:
                amount = int(amount_str)
                if 'thousand' in response_lower or 'k' in response_lower[amount_match.end():amount_match.end()+5]:
                    amount *= 1000
            except ValueError:
                pass

        # Try to extract equity
        equity_match = re.search(r'(\d+)\s*(?:%|percent)', response_lower)
        equity = None
        if equity_match:
            try:
                equity = int(equity_match.group(1))
            except ValueError:
                pass

        # Try to extract royalty (for Victor)
        royalty = None
        royalty_until = None
        if shark_id == 'victor' or 'royalty' in response_lower:
            royalty_match = re.search(r'\$?([\d.]+)\s*(?:per unit|royalty)', response_lower)
            if royalty_match:
                try:
                    royalty = float(royalty_match.group(1))
                    royalty_until = pitch_data.get('amountRaising', 100000)
                except ValueError:
                    pass

        # If we found meaningful terms, create an offer
        if amount or equity:
            return {
                'sharkId': shark_id,
                'sharkName': self.get_shark_name(shark_id),
                'amount': amount or pitch_data.get('amountRaising', 100000),
                'equity': equity or pitch_data.get('equityPercent', 10) + 5,
                'royalty': royalty,
                'royaltyUntil': royalty_until,
                'conditions': []
            }

        return None
