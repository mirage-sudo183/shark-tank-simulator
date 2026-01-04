"""
Claude API Client for Shark Tank Simulator
Handles AI-powered shark responses
"""

import anthropic
import httpx
import time


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
                                 context, confidence, user_message=None):
        """Generate a shark response based on the pitch and context."""
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
"""

        if user_message:
            user_prompt += f"\nTHE ENTREPRENEUR JUST SAID: \"{user_message}\"\n"

        user_prompt += """
Respond in character. You may:
1. Ask a pointed question about the business
2. Express skepticism or genuine interest
3. Make an offer if you're very interested (include specific terms: amount and equity percentage)
4. Declare "I'm out" if you're not interested (include a reason)

Keep your response to 2-3 sentences maximum. Be authentic to your character. Do not be overly verbose."""

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
