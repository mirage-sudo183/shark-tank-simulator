#!/usr/bin/env python3
"""Test script to verify counter offer response parsing logic."""

import re

def parse_counter_response(response_text):
    """Simulates the parsing logic from ai_client.py"""

    # Parse the response type from tag
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
        accept_phrases = ["you've got a deal", "it's a deal", "we have a deal",
                          'shake on it', 'agreed', "let's do it", "you got a deal"]
        if any(phrase in response_text.lower() for phrase in accept_phrases):
            if 'no deal' not in response_text.lower():
                response_type = 'ACCEPT'

        # Check for rejection phrases as backup
        if "i'm out" in response_text.lower() or "im out" in response_text.lower():
            response_type = 'REJECT'

    return response_type, clean_response


# Test cases
test_cases = [
    # Case 1: Victor's royalty deal scenario (the bug)
    {
        "name": "Victor royalty deal (should NOT be ACCEPT)",
        "response": "Hold on there - I didn't offer you equity, I offered you a royalty deal. One hundred thousand for two dollars per unit sold until I get my money back plus twenty percent return. Are you willing to do the royalty structure or not? [COUNTER_ACTION: ADJUST_STRUCTURE]",
        "expected": "ADJUST_STRUCTURE"
    },

    # Case 2: Actual acceptance
    {
        "name": "Clear acceptance with tag",
        "response": "Alright, you drive a hard bargain but you've got a deal! Let's shake on it. [COUNTER_ACTION: ACCEPT]",
        "expected": "ACCEPT"
    },

    # Case 3: Acceptance without tag (fallback)
    {
        "name": "Acceptance without tag (fallback detection)",
        "response": "Fine, you've got a deal! Let's do this.",
        "expected": "ACCEPT"
    },

    # Case 4: Rejection
    {
        "name": "Shark goes out",
        "response": "That's way too rich for me. I'm out. [COUNTER_ACTION: REJECT]",
        "expected": "REJECT"
    },

    # Case 5: Meet halfway
    {
        "name": "Meet halfway counter",
        "response": "I can't do 10%, but I'll meet you in the middle at 15% for the same $100,000. [COUNTER_ACTION: MEET_HALFWAY]",
        "expected": "MEET_HALFWAY"
    },

    # Case 6: Restate conditions
    {
        "name": "Restate conditions",
        "response": "I hear what you're saying, but I still need to see those sales numbers before I commit. [COUNTER_ACTION: RESTATE_CONDITIONS]",
        "expected": "RESTATE_CONDITIONS"
    },

    # Case 7: Deal structure mention without acceptance
    {
        "name": "Mentions 'deal' but not accepting",
        "response": "This deal structure doesn't work for me. Let's talk about a licensing deal instead. [COUNTER_ACTION: ADJUST_STRUCTURE]",
        "expected": "ADJUST_STRUCTURE"
    },

    # Case 8: No tag, mentions deal generically (should NOT accept)
    {
        "name": "Generic 'deal' mention without tag",
        "response": "I like this deal but I need to think about the structure more.",
        "expected": "REJECT"  # Default when no clear signal
    },

    # Case 9: "It's a deal" without tag
    {
        "name": "It's a deal without tag",
        "response": "Okay, it's a deal! Welcome to the family.",
        "expected": "ACCEPT"
    },
]


def run_tests():
    print("=" * 60)
    print("COUNTER OFFER PARSING TEST")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        result, _ = parse_counter_response(test["response"])
        status = "PASS" if result == test["expected"] else "FAIL"

        if status == "PASS":
            passed += 1
            print(f"\n[{status}] Test {i}: {test['name']}")
            print(f"       Expected: {test['expected']}, Got: {result}")
        else:
            failed += 1
            print(f"\n[{status}] Test {i}: {test['name']}")
            print(f"       Expected: {test['expected']}, Got: {result}")
            print(f"       Response: {test['response'][:80]}...")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
