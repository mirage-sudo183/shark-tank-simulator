"""
Claude API Client for Shark Tank Simulator
Handles AI-powered shark responses with belief-consistent behavior
"""

import anthropic
import httpx
import time
import re
import json

from sharks import INVESTOR_ARCHETYPES, DEAL_TYPES


class AIClient:
    """Client for generating AI shark responses using Claude."""

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = None
        self.max_retries = 3
        self.retry_delay = 1  # seconds

        if api_key:
            # Configure with custom httpx client for Railway compatibility
            http_client = httpx.Client(
                timeout=httpx.Timeout(60.0, connect=30.0),
                follow_redirects=True,
            )
            self.client = anthropic.Anthropic(
                api_key=api_key,
                http_client=http_client,
            )
            print("[AI] Anthropic client initialized with custom HTTP client")
        else:
            print("[AI] No API key provided - using fallback responses")

    def _format_transcript(self, transcript):
        """Format pitch transcript for the prompt."""
        if not transcript:
            return "(No transcript available)"

        lines = []
        for entry in transcript:  # Include full pitch transcript
            text = entry.get('text', '')
            if text:
                lines.append(f"- {text}")

        return '\n'.join(lines) if lines else "(No speech captured)"

    def _format_context(self, context):
        """Format Q&A context for the prompt."""
        if not context:
            return "(Start of Q&A session)"

        lines = []
        for entry in context[-10:]:  # Last 10 messages
            speaker = entry.get('speaker', 'Unknown')
            text = entry.get('text', '')
            if text:
                lines.append(f"{speaker}: {text}")

        return '\n'.join(lines) if lines else "(No prior conversation)"

    def generate_shark_response(self, shark_id, persona, pitch_data, transcript,
                                 context, confidence, user_message=None, belief_state=None,
                                 deal_context=None):
        """Generate a shark response based on the pitch, context, belief state, and deal mode."""
        if not self.client:
            # Return a fallback response if no API key
            return self._get_fallback_response(shark_id, confidence)

        # Build the prompt
        company_name = pitch_data.get('companyName', 'the company')
        amount = pitch_data.get('amountRaising', 0)
        equity = pitch_data.get('equityPercent', 0)
        description = pitch_data.get('companyDescription', '')
        proof_type = pitch_data.get('proofType', 'idea')
        proof_value = pitch_data.get('proofValue', '')
        why_now = pitch_data.get('whyNow', '')

        # Get archetype info
        archetype = INVESTOR_ARCHETYPES.get(shark_id, {})
        allowed_deals = archetype.get('allowed_deals', ['cash_equity'])
        disallowed_deals = archetype.get('disallowed_deals', [])

        # Format belief state for prompt
        belief_context = self._format_belief_state(belief_state) if belief_state else ""

        # Format deal context (competing offers, deal mode, etc.)
        deal_context_str = self._format_deal_context(deal_context) if deal_context else ""

        user_prompt = f"""You are on Shark Tank evaluating a pitch.

PITCH SUMMARY:
- Company: {company_name}
- Asking: ${amount:,} for {equity}% equity
- Description: {description}
- Traction: {proof_type} - {proof_value if proof_value else 'None stated'}
- Why now: {why_now}

PITCH TRANSCRIPT:
{self._format_transcript(transcript)}

CONVERSATION SO FAR:
{self._format_context(context)}

YOUR CURRENT INTEREST LEVEL: {confidence}/100
{belief_context}{deal_context_str}
INVESTOR CONSTRAINTS:
- Allowed deal types: {', '.join(allowed_deals)}
- Disallowed deal types: {', '.join(disallowed_deals) if disallowed_deals else 'None'}
"""

        if user_message:
            user_prompt += f"\nTHE ENTREPRENEUR JUST SAID: \"{user_message}\"\n"

        user_prompt += """
Respond in character. Your response MUST be one of these action types:
1. ASK - Ask a pointed question to gather information
2. EXPRESS - Share your opinion, concern, or praise about the business
3. CONDITIONAL_OFFER - Make an offer with conditions or milestones attached
4. IMMEDIATE_OFFER - Make a direct cash-for-equity offer (only if confidence is high and you have no outstanding concerns)
5. REJECT - Declare "I'm out" with a specific reason

IMPORTANT RULES:
- If you have stated concerns that haven't been addressed, you CANNOT make an IMMEDIATE_OFFER
- If you've asked for proof/traction, you must see it before making unconditional offers
- Your offer terms MUST be consistent with your stated concerns and beliefs
- If there are competing offers, consider whether to beat them or hold firm
- If the founder just satisfied one of your proof requirements, acknowledge it and consider improving your position
- Keep your response to 2-3 sentences maximum
- Be authentic to your character

End your response with one of these tags to indicate your action:
[ACTION: ASK], [ACTION: EXPRESS], [ACTION: CONDITIONAL_OFFER], [ACTION: IMMEDIATE_OFFER], or [ACTION: REJECT]"""

        # Retry logic for connection issues
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=200,
                    system=persona,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                return response.content[0].text.strip()

            except anthropic.APIConnectionError as e:
                last_error = e
                print(f"[AI] Connection error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                continue
            except anthropic.RateLimitError as e:
                print(f"[AI] Rate limit exceeded: {e}")
                return self._get_fallback_response(shark_id, confidence)
            except anthropic.AuthenticationError as e:
                print(f"[AI] Authentication error - check API key: {e}")
                return self._get_fallback_response(shark_id, confidence)
            except Exception as e:
                print(f"[AI] Error generating response: {type(e).__name__}: {e}")
                return self._get_fallback_response(shark_id, confidence)

        # All retries failed
        print(f"[AI] All {self.max_retries} retries failed, using fallback")
        return self._get_fallback_response(shark_id, confidence)

    def generate_offer_dialogue(self, shark_id, persona, offer_terms, pitch_data, context=None):
        """
        Generate dialogue for a shark making an offer with specific pre-determined terms.
        This ensures the spoken offer matches the panel exactly.
        """
        if not self.client:
            # Fallback with exact terms
            amount = offer_terms.get('amount', 0)
            equity = offer_terms.get('equity', 0)
            return f"I'll give you ${amount:,} for {equity}% equity. [ACTION: IMMEDIATE_OFFER]"

        company_name = pitch_data.get('companyName', 'the company')
        amount = offer_terms.get('amount', 0)
        equity = offer_terms.get('equity', 0)
        deal_type = offer_terms.get('deal_type', 'cash_equity')
        conditions = offer_terms.get('conditions', [])
        royalty = offer_terms.get('royalty')

        # Build terms description
        terms_desc = f"${amount:,} for {equity}%"
        if royalty:
            terms_desc += f" plus ${royalty} per unit royalty"
        if conditions:
            terms_desc += f" with conditions: {', '.join(conditions)}"

        context_str = self._format_context(context) if context else ""

        user_prompt = f"""You are making an offer on Shark Tank for {company_name}.

YOUR OFFER TERMS (use these EXACT numbers):
- Amount: ${amount:,}
- Equity: {equity}%
{f'- Royalty: ${royalty} per unit' if royalty else ''}
{f'- Conditions: {", ".join(conditions)}' if conditions else ''}
- Deal type: {deal_type}

RECENT CONVERSATION:
{context_str}

Generate a 1-2 sentence offer statement in your character's voice.
You MUST state the exact offer terms: ${amount:,} for {equity}%.
Be enthusiastic but authentic to your personality.
Do NOT change the numbers - use exactly ${amount:,} for {equity}%.

End with [ACTION: {'CONDITIONAL_OFFER' if conditions else 'IMMEDIATE_OFFER'}]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                system=persona,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating offer dialogue: {e}")
            # Fallback with exact terms
            return f"I'll give you ${amount:,} for {equity}% equity. [ACTION: IMMEDIATE_OFFER]"

    def generate_decline_response(self, shark_id, persona, original_offer):
        """Generate a response when the user declines an offer."""
        if not self.client:
            return self._get_decline_fallback(shark_id)

        amount = original_offer.get('amount', 0)
        equity = original_offer.get('equity', 0)

        user_prompt = f"""The entrepreneur just declined your offer of ${amount:,} for {equity}% equity.

Express your disappointment or make a final statement in character. Keep it to 1-2 sentences. You can either:
1. Wish them luck and bow out gracefully
2. Express frustration that they're making a mistake
3. Make one final push with slightly improved terms

Stay in character."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                system=persona,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            return response.content[0].text.strip()

        except Exception as e:
            print(f"Error generating decline response: {e}")
            return self._get_decline_fallback(shark_id)

    def generate_counter_response(self, shark_id, persona, original_offer, counter_terms, pitch_data):
        """Generate a response to a counter offer. Returns (response_text, accepts_counter)."""
        if not self.client:
            return self._get_counter_fallback(shark_id), False

        original_amount = original_offer.get('amount', 0)
        original_equity = original_offer.get('equity', 0)
        counter_amount = counter_terms.get('amount', original_amount)
        counter_equity = counter_terms.get('equity', original_equity)

        user_prompt = f"""You offered ${original_amount:,} for {original_equity}% equity.

The entrepreneur countered with: ${counter_amount:,} for {counter_equity}% equity.

Evaluate this counter-offer and respond in character. You can:
1. ACCEPT the counter (say "You've got a deal!" or similar)
2. REJECT and go out (you've had enough negotiating)
3. Make a FINAL counter-offer (meet in the middle)

Consider:
- Is the valuation reasonable?
- How much do you want this deal?
- Would you walk away from this?

Keep response to 2-3 sentences. End with clear indication of your decision."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                system=persona,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text.strip()

            # Check if they accepted
            accept_phrases = ['deal', 'accept', "you've got", 'shake on it', 'agreed',
                             "let's do it", "i'm in", 'done']
            accepts = any(phrase in response_text.lower() for phrase in accept_phrases)

            # But not if they said "no deal"
            if 'no deal' in response_text.lower():
                accepts = False

            return response_text, accepts

        except Exception as e:
            print(f"Error generating counter response: {e}")
            return self._get_counter_fallback(shark_id), False

    def _get_fallback_response(self, shark_id, confidence):
        """Get a fallback response when API is unavailable."""
        fallbacks = {
            'marcus': [
                "Walk me through the unit economics. What's your CAC and LTV?",
                "How does this scale? What happens when you hit a million users?",
                "Who's your biggest competitor and why will you crush them?"
            ],
            'victor': [
                "What are your sales? I need to see the numbers.",
                "How much does it cost you to make one unit? What's your margin?",
                "Why should I invest my money here instead of a boring index fund?"
            ],
            'elena': [
                "Is this patented? Do you have any protection?",
                "Have you sold this in retail stores yet?",
                "Can you demonstrate how this works for the customer?"
            ],
            'richard': [
                "Tell me about the customer experience from start to finish.",
                "What's the story behind this brand? Why does it exist?",
                "How are you disrupting the way things are currently done?"
            ],
            'daniel': [
                "Tell me about yourself. How did you get here?",
                "Is this recurring revenue or one-time purchases?",
                "What keeps you up at night about this business?"
            ]
        }

        import random
        return random.choice(fallbacks.get(shark_id, ["Tell me more about your business."]))

    def _get_decline_fallback(self, shark_id):
        """Get a fallback response when user declines."""
        fallbacks = {
            'marcus': "You're making a mistake. Good luck.",
            'victor': "Fine. Your loss. This deal is dead to me.",
            'elena': "I wish you the best. I hope you find the right partner.",
            'richard': "I respect your decision. Keep chasing that dream.",
            'daniel': "I understand. I really do wish you success."
        }
        return fallbacks.get(shark_id, "Good luck.")

    def _get_counter_fallback(self, shark_id):
        """Get a fallback response to counter offers."""
        fallbacks = {
            'marcus': "That's not going to work for me. My offer stands.",
            'victor': "You're pushing too hard. Take the deal or leave it.",
            'elena': "I appreciate the negotiation, but I need my terms.",
            'richard': "I like the hustle, but let's meet somewhere in the middle.",
            'daniel': "I want to make this work. Let me think about it."
        }
        return fallbacks.get(shark_id, "Let me think about that.")

    def _format_belief_state(self, belief_state):
        """Format belief state for inclusion in prompt."""
        if not belief_state:
            return ""

        # Handle both dict and object
        if hasattr(belief_state, 'to_dict'):
            bs = belief_state.to_dict()
        else:
            bs = belief_state

        lines = ["\nYOUR CURRENT BELIEFS ABOUT THIS PITCH:"]

        perceived_stage = bs.get('perceived_stage', 'unknown')
        lines.append(f"- Perceived company stage: {perceived_stage}")

        conviction = bs.get('capital_conviction', 'low')
        lines.append(f"- Your investment conviction: {conviction}")

        concerns = bs.get('stated_concerns', [])
        if concerns:
            lines.append(f"- Concerns you've expressed: {', '.join(concerns)}")

        positives = bs.get('stated_positives', [])
        if positives:
            lines.append(f"- Positives you've noted: {', '.join(positives)}")

        required_proof = bs.get('required_proof', [])
        if required_proof:
            lines.append(f"- Proof you're waiting for: {', '.join(required_proof)}")

        key_risks = bs.get('key_risks', [])
        if key_risks:
            lines.append(f"- Key risks identified: {', '.join(key_risks)}")

        val_range = bs.get('implied_valuation_range', [0, 0])
        if val_range[1] > 0:
            lines.append(f"- Your implied valuation range: ${val_range[0]:,.0f} - ${val_range[1]:,.0f}")

        return '\n'.join(lines) + '\n'

    def _format_deal_context(self, deal_context):
        """Format deal context for inclusion in prompt."""
        if not deal_context:
            return ""

        lines = ["\nCURRENT DEAL SITUATION:"]

        # Deal mode
        mode = deal_context.get('deal_mode', 'exploration')
        mode_descriptions = {
            'exploration': 'Early Q&A phase - no offers on the table yet',
            'single_offer': 'One shark has made an offer',
            'bidding_war': 'Multiple sharks competing for this deal!',
            'final_offer': 'Final offer mode - decision time',
            'closed': 'Deal has been closed'
        }
        lines.append(f"- Deal status: {mode_descriptions.get(mode, mode)}")

        # Competing offers
        competing = deal_context.get('competing_offers', [])
        if competing:
            lines.append(f"- COMPETING OFFERS ON THE TABLE:")
            for offer in competing[:3]:  # Show up to 3 competing offers
                shark_name = offer.get('sharkName', 'Another shark')
                amount = offer.get('amount', 0)
                equity = offer.get('equity', 0)
                deal_type = offer.get('deal_type', 'cash_equity')
                lines.append(f"  * {shark_name}: ${amount:,} for {equity}% ({deal_type})")
            lines.append("  Consider whether to beat these offers or differentiate your value!")

        # If in bidding war
        if deal_context.get('is_bidding_war'):
            lines.append("- WARNING: This is now a BIDDING WAR - decide if you want to compete or withdraw")

        # Proofs just satisfied
        proofs = deal_context.get('proofs_just_satisfied', [])
        if proofs:
            lines.append(f"- PROOF JUST PROVIDED BY FOUNDER: {', '.join(str(p) for p in proofs)}")
            lines.append("  This answers questions you may have asked - acknowledge and potentially improve your terms!")

        return '\n'.join(lines) + '\n'

    def parse_structured_response(self, response_text):
        """
        Parse a structured shark response to extract action type and content.
        Returns dict with: action_type, content, concerns, positives, etc.
        """
        result = {
            'action_type': 'EXPRESS',  # Default
            'content': response_text,
            'raw_response': response_text,
            'concerns': [],
            'positives': [],
            'required_proof': [],
            'is_offer': False,
            'is_rejection': False
        }

        # Extract action tag
        action_match = re.search(r'\[ACTION:\s*(\w+)\]', response_text, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).upper()
            if action in ['ASK', 'EXPRESS', 'CONDITIONAL_OFFER', 'IMMEDIATE_OFFER', 'REJECT']:
                result['action_type'] = action

            # Remove the action tag from content
            result['content'] = re.sub(r'\[ACTION:\s*\w+\]', '', response_text).strip()

        # Detect offer intent
        offer_phrases = ['offer', "i'll give you", 'deal:', 'here\'s what i\'ll do',
                        'i\'m in for', 'investment of', "here's my offer",
                        "i'll do", "let me make you"]
        if any(phrase in response_text.lower() for phrase in offer_phrases):
            result['is_offer'] = True
            if result['action_type'] == 'EXPRESS':
                # Auto-detect as offer if phrases present
                result['action_type'] = 'IMMEDIATE_OFFER'

        # Detect rejection
        out_phrases = ["i'm out", "im out", "i am out", "count me out", "i have to pass"]
        if any(phrase in response_text.lower() for phrase in out_phrases):
            result['is_rejection'] = True
            result['action_type'] = 'REJECT'

        # Extract concerns (things they're worried about)
        concern_patterns = [
            r"(?:i'm (?:worried|concerned) about|my concern is|the problem is|i don't (?:see|understand|like))\s+([^.!?]+)",
            r"(?:valuation (?:is|seems)|pricing (?:is|seems))\s+([^.!?]+)",
            r"(?:need to see|want to see|show me)\s+([^.!?]+)"
        ]
        for pattern in concern_patterns:
            matches = re.findall(pattern, response_text.lower())
            result['concerns'].extend([m.strip() for m in matches])

        # Extract positives (things they like)
        positive_patterns = [
            r"(?:i (?:love|like|appreciate)|this is (?:great|excellent|impressive))\s+([^.!?]+)",
            r"(?:strong|impressive|solid)\s+([^.!?]+)"
        ]
        for pattern in positive_patterns:
            matches = re.findall(pattern, response_text.lower())
            result['positives'].extend([m.strip() for m in matches])

        # Extract proof requirements
        proof_patterns = [
            r"(?:need to see|want to see|show me|come back when you have)\s+([^.!?]+)",
            r"(?:if you can|once you have|when you reach)\s+([^.!?]+)"
        ]
        for pattern in proof_patterns:
            matches = re.findall(pattern, response_text.lower())
            result['required_proof'].extend([m.strip() for m in matches])

        return result

    def generate_strategic_counter_response(self, shark_id, persona, original_offer,
                                            counter_terms, pitch_data, belief_state=None):
        """
        Generate a strategic response to a counter offer.
        Returns (response_text, response_type, new_terms) where response_type is one of:
        ACCEPT, REJECT, MEET_HALFWAY, ADJUST_STRUCTURE, RESTATE_CONDITIONS
        """
        if not self.client:
            return self._get_counter_fallback(shark_id), 'REJECT', None

        original_amount = original_offer.get('amount', 0)
        original_equity = original_offer.get('equity', 0)
        original_type = original_offer.get('deal_type', 'cash_equity')
        counter_amount = counter_terms.get('amount', original_amount)
        counter_equity = counter_terms.get('equity', original_equity)

        # Calculate implied valuations
        orig_val = original_amount / (original_equity / 100) if original_equity > 0 else 0
        counter_val = counter_amount / (counter_equity / 100) if counter_equity > 0 else 0

        # Format belief state
        belief_context = self._format_belief_state(belief_state) if belief_state else ""

        # Get archetype info
        archetype = INVESTOR_ARCHETYPES.get(shark_id, {})
        allowed_deals = archetype.get('allowed_deals', ['cash_equity'])

        user_prompt = f"""You offered ${original_amount:,} for {original_equity}% equity (deal type: {original_type}).
Your offer implied a valuation of ${orig_val:,.0f}.

The entrepreneur countered with: ${counter_amount:,} for {counter_equity}% equity.
Their counter implies a valuation of ${counter_val:,.0f}.

{belief_context}
This counter-offer is a STRATEGIC SIGNAL. Consider:
1. What is the founder implying about their confidence?
2. What are they trying to protect (valuation, equity, control)?
3. Is their position reasonable given the dialogue so far?
4. Does this contradict any concerns you've stated?

You MUST respond with ONE of these approaches:
1. ACCEPT - The counter is reasonable, accept it (say "You've got a deal!" clearly)
2. REJECT - You've had enough, go out (say "I'm out" clearly)
3. MEET_HALFWAY - Propose specific compromise terms
4. ADJUST_STRUCTURE - Suggest a different deal structure (e.g., "Let's do a royalty instead")
5. RESTATE_CONDITIONS - "I hear you, but I still need to see X first"

Your allowed deal structures are: {', '.join(allowed_deals)}

Keep response to 2-3 sentences. End with [COUNTER_ACTION: TYPE] tag."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=250,
                system=persona,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse the response type
            action_match = re.search(r'\[COUNTER_ACTION:\s*(\w+)\]', response_text, re.IGNORECASE)
            response_type = 'REJECT'  # Default
            if action_match:
                action = action_match.group(1).upper()
                if action in ['ACCEPT', 'REJECT', 'MEET_HALFWAY', 'ADJUST_STRUCTURE', 'RESTATE_CONDITIONS']:
                    response_type = action

            # Clean the response
            clean_response = re.sub(r'\[COUNTER_ACTION:\s*\w+\]', '', response_text).strip()

            # Only use phrase detection as fallback when no valid action tag was found
            if not action_match:
                # Check for acceptance phrases as backup - use specific phrases to avoid false positives
                # (e.g., "royalty deal" should not trigger acceptance)
                accept_phrases = ["you've got a deal", "it's a deal", "we have a deal",
                                  'shake on it', 'agreed', "let's do it", "you got a deal"]
                if any(phrase in response_text.lower() for phrase in accept_phrases):
                    if 'no deal' not in response_text.lower():
                        response_type = 'ACCEPT'

                # Check for rejection phrases as backup
                if "i'm out" in response_text.lower() or "im out" in response_text.lower():
                    response_type = 'REJECT'

            # Extract new terms if MEET_HALFWAY
            new_terms = None
            if response_type == 'MEET_HALFWAY':
                # Try to extract new terms from response
                amount_match = re.search(r'\$?([\d,]+)(?:k|K)?', clean_response)
                equity_match = re.search(r'(\d+(?:\.\d+)?)\s*%', clean_response)

                if amount_match and equity_match:
                    new_amount = int(amount_match.group(1).replace(',', ''))
                    if 'k' in response_text.lower() or 'K' in response_text:
                        new_amount *= 1000
                    new_terms = {
                        'amount': new_amount,
                        'equity': float(equity_match.group(1))
                    }

            return clean_response, response_type, new_terms

        except Exception as e:
            print(f"Error generating strategic counter response: {e}")
            return self._get_counter_fallback(shark_id), 'REJECT', None
