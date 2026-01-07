# Known Issues & Bug Fixes

This document tracks issues identified during testing and their resolution status.

---

## Resolved Issues

### 1. False Deal Acceptance on "Royalty Deal" Phrase
**Status:** FIXED

**Problem:** When a shark mentioned "royalty deal" in their response (e.g., "I offered you a royalty deal"), the app incorrectly parsed this as an ACCEPT action, triggering a false deal closure.

**Root Cause:** The phrase detection backup in `ai_client.py` used generic phrases like `'deal'` which matched "royalty deal", "deal structure", etc.

**Fix:**
- Changed accept phrases to be more specific: `"you've got a deal"`, `"it's a deal"`, `"we have a deal"`, etc.
- Made phrase detection only run as fallback when no `[COUNTER_ACTION:]` tag is found

**File:** `server/ai_client.py` (lines 605-616)

---

### 2. Royalty Deal Shown as "Equity Deal" in UI
**Status:** FIXED

**Problem:** When Victor countered with a royalty deal structure, it was displayed as "Cash for Equity" instead of "Royalty Deal" in the offers panel.

**Root Cause:** In `MEET_HALFWAY` response handling, the `deal_type` was copied from the original offer which might not have had `deal_type` set, defaulting to `'cash_equity'`.

**Fix:**
- Added explicit check for Victor to use `'royalty'` deal type
- Added error handling and debug logging for offer creation

**Files:** `server/app.py` (lines 1176-1197, 1209-1221)

---

### 3. Acceptance Getting Stuck
**Status:** FIXED

**Problem:** When accepting an offer (especially after counter-offers), the simulation would get stuck instead of showing the deal closed screen.

**Root Cause:**
- Backend could return 404 if offer wasn't found
- Frontend didn't handle error responses, just silently failed

**Fix:**
- Added error handling in frontend `acceptOffer()` function
- Falls back to closing deal with local offer data if backend fails
- Added duplicate overlay prevention

**File:** `app.js` (lines 2575-2647, 2781-2837)

---

### 4. Deal Closed Popup Disappearing
**Status:** FIXED

**Problem:** The deal closed popup appeared to disappear quickly.

**Root Cause:** Potential duplicate overlays being created from multiple event sources (SSE + API fallback).

**Fix:**
- Added check to prevent duplicate overlays
- Set explicit z-index (9999) to ensure overlay stays on top
- Added unique ID to overlay element

**File:** `app.js` (lines 2781-2837)

---

### 5. Counter Offer Modal Missing Royalty Fields
**Status:** FIXED

**Problem:** When countering a royalty deal, the modal only showed Amount and Equity fields - no way to counter on royalty terms.

**Fix:**
- Added "Royalty per unit" field to counter offer modal
- Field shows/hides based on deal type
- Counter terms now include royalty when applicable

**Files:**
- `index.html` (lines 488-496)
- `app.js` (lines 2716-2725, 2750-2753)

---

### 6. Offer Card Buttons Not Fitting
**Status:** FIXED

**Problem:** The 4 buttons (Accept, Counter, Decline, Reply) in offer cards didn't fit well in the chat window.

**Fix:**
- Changed from flex to 2x2 grid layout
- Reduced button padding and font size

**File:** `styles.css` (lines 1619-1636)

---

### 7. Counter Modal Not Showing Original Offer
**Status:** FIXED

**Problem:** When opening the counter modal, it wasn't clear what the original offer was.

**Fix:**
- Added "Their offer:" display section at top of modal
- Shows amount, equity, royalty (if applicable), and deal type

**Files:**
- `index.html` (lines 471-475)
- `styles.css` (lines 1761-1783)
- `app.js` (lines 2687-2704)

---

### 8. Limited Quick Test Options
**Status:** FIXED

**Problem:** Quick Test mode only tested with Victor, no way to test other sharks' offer styles.

**Fix:**
- Added shark selection dropdown to Quick Test section
- Backend accepts `sharkId` parameter
- Updated belief states for proper offer generation

**Files:**
- `index.html` (lines 219-232)
- `styles.css` (lines 349-392)
- `app.js` (lines 870-879)
- `server/app.py` (lines 266-332)

---

## Testing

### Unit Tests
```bash
cd server
python3 test_counter_parsing.py  # Test counter offer parsing
python3 test_deal_type.py        # Test Victor's royalty deal type
```

### Manual Testing
1. Go to https://127.0.0.1:8443
2. Use Quick Test mode with different sharks
3. Test counter offers on royalty deals
4. Verify deal acceptance works properly

---

## Shark Deal Types Reference

| Shark | Preferred Deal Type | Notes |
|-------|---------------------|-------|
| Victor Slate | Royalty | Loves cash flow, $X/unit until recouped |
| Marcus Kellan | Cash Equity | Tech-focused, hates royalty |
| Elena Brooks | SAFE + Milestone | Needs proof/traction |
| Richard Sterling | Cash Equity | Brand/vision focused |
| Daniel Chen | Tranche/Milestone | Mentor-style, staged investments |
