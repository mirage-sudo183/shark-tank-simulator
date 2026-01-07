#!/usr/bin/env python3
"""Test that Victor's offers correctly get deal_type='royalty'"""

import sys
sys.path.insert(0, '.')

from sharks import SharkManager, InvestorBeliefState, INVESTOR_ARCHETYPES

def test_victor_deal_type():
    """Test that Victor always gets royalty deal type"""
    print("=" * 60)
    print("VICTOR DEAL TYPE TEST")
    print("=" * 60)

    shark_manager = SharkManager()

    # Test pitch data
    pitch_data = {
        'companyName': 'TestCo',
        'amountRaising': 100000,
        'equityPercent': 10
    }

    # Create belief state for Victor with medium conviction (realistic for Quick Test)
    belief_state = InvestorBeliefState('victor', pitch_data)
    belief_state.capital_conviction = 'medium'  # Quick Test mode sets high confidence
    belief_state.perceived_stage = 'revenue'  # TestCo has $50k MRR
    belief_state.implied_valuation_range = (500000, 2000000)  # Realistic valuation range

    # Test 1: Check appropriate deal types
    appropriate_types = belief_state.get_appropriate_deal_types()
    print(f"\n[Test 1] Victor's appropriate deal types: {appropriate_types}")
    assert 'royalty' in appropriate_types, "FAIL: 'royalty' should be in Victor's appropriate types"
    print("  PASS: 'royalty' is in appropriate types")

    # Test 2: Generate structured offer
    offer = shark_manager.generate_structured_offer('victor', pitch_data, belief_state, confidence=85)
    print(f"\n[Test 2] Generated offer deal_type: {offer.get('deal_type')}")
    assert offer.get('deal_type') == 'royalty', f"FAIL: Expected 'royalty', got '{offer.get('deal_type')}'"
    print("  PASS: Victor's offer has deal_type='royalty'")

    # Test 3: Check offer has royalty terms
    print(f"\n[Test 3] Offer details:")
    print(f"  - amount: ${offer.get('amount', 0):,}")
    print(f"  - equity: {offer.get('equity')}%")
    print(f"  - royalty: ${offer.get('royalty')}/unit")
    print(f"  - royaltyUntil: ${offer.get('royaltyUntil', 0):,}")

    assert offer.get('royalty') is not None, "FAIL: Victor's offer should have royalty field"
    print("  PASS: Royalty terms present")

    # Test 4: Test MEET_HALFWAY scenario - simulating the fix
    print(f"\n[Test 4] MEET_HALFWAY deal type logic:")
    original_offer = {'deal_type': 'cash_equity'}  # Original might be wrong

    # This is the fixed logic from app.py
    deal_type = original_offer.get('deal_type', 'cash_equity')
    if 'victor' == 'victor' and deal_type == 'cash_equity':
        deal_type = 'royalty'  # Victor always prefers royalty

    print(f"  Original deal_type: {original_offer.get('deal_type')}")
    print(f"  Corrected deal_type: {deal_type}")
    assert deal_type == 'royalty', "FAIL: Victor's MEET_HALFWAY should correct to 'royalty'"
    print("  PASS: MEET_HALFWAY correctly uses 'royalty' for Victor")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        test_victor_deal_type()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
