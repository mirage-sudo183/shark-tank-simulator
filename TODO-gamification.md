# Gamification Features TODO

## Overview
Add game mechanics to increase engagement, retention, and virality. Make pitching addictive.

---

## 1. Achievement System

### Pitch Achievements
- [ ] **First Blood** - Get your first offer
- [ ] **Shark Slayer** - Get offers from all 5 sharks in one session
- [ ] **Smooth Talker** - Close a deal without any shark going out
- [ ] **Comeback Kid** - Get a deal after 3+ sharks went out
- [ ] **Unicorn Hunter** - Get a $10M+ valuation
- [ ] **Bootstrapper** - Close a deal giving up less than 10% equity
- [ ] **Whale Catcher** - Get Mr. Wonderful to say something nice

### Streak Achievements
- [ ] **On Fire** - 3 deals in a row
- [ ] **Unstoppable** - 5 deals in a row
- [ ] **Legendary** - 10 deals in a row

### Special Achievements
- [ ] **Speed Demon** - Close a deal in under 2 minutes
- [ ] **Marathon Pitcher** - Survive 15+ minutes of Q&A
- [ ] **Bidding War Victor** - Win a bidding war between 3+ sharks
- [ ] **Negotiator** - Successfully counter-offer 3 times

### Implementation
- Store achievements in Firestore per user
- Show achievement popup when unlocked
- Display achievement badges on profile/leaderboard
- Add achievement showcase on deal card

---

## 2. XP & Leveling System

### XP Sources
- [ ] Complete a pitch session: +100 XP
- [ ] Get an offer: +50 XP per offer
- [ ] Close a deal: +200 XP
- [ ] Win a bidding war: +150 XP
- [ ] Get all sharks interested (confidence > 70): +100 XP
- [ ] Daily login bonus: +25 XP

### Levels
```
Level 1: Dreamer (0 XP)
Level 2: Hustler (500 XP)
Level 3: Entrepreneur (1,500 XP)
Level 4: Founder (3,500 XP)
Level 5: CEO (7,000 XP)
Level 6: Unicorn (15,000 XP)
Level 7: Decacorn (30,000 XP)
Level 8: Legend (50,000 XP)
```

### Level Perks
- [ ] Level 3: Unlock "Investor Insights" - see shark preferences before pitch
- [ ] Level 5: Unlock "Second Chance" - restart Q&A once per session
- [ ] Level 7: Unlock "Shark Whisperer" - see exact confidence numbers

---

## 3. Daily Challenges

### Challenge Types
- [ ] **Daily Deal** - Close any deal today (+50 XP bonus)
- [ ] **Tough Crowd** - Get a deal with Kevin O'Leary (+75 XP)
- [ ] **High Roller** - Get an offer over $500K (+60 XP)
- [ ] **Equity Saver** - Close a deal under 15% equity (+80 XP)
- [ ] **Quick Pitch** - End pitch phase in under 60 seconds (+40 XP)

### Implementation
- Generate 3 random challenges daily
- Show challenges on dashboard before pitch
- Track progress during session
- Award bonus XP on completion

---

## 4. Leaderboard Enhancements

### Multiple Leaderboards
- [ ] **Weekly** - Resets every Monday
- [ ] **All-Time** - Permanent rankings
- [ ] **Best Valuation** - Highest implied valuation deals
- [ ] **Deal Volume** - Most deals closed
- [ ] **Shark Favorites** - Most offers received

### Leaderboard Rewards
- [ ] Top 10 weekly: Special badge
- [ ] #1 weekly: "Shark Tank Champion" title
- [ ] Top 100 all-time: Gold border on profile

---

## 5. Pitch Streaks

### Streak Tracking
- [ ] Track consecutive days with at least one pitch
- [ ] Show streak counter on dashboard
- [ ] Streak milestones: 3, 7, 14, 30, 100 days

### Streak Rewards
- [ ] 7-day streak: +100 XP bonus
- [ ] 30-day streak: Exclusive "Dedicated Founder" badge
- [ ] 100-day streak: "Pitch Legend" title + gold shark icon

### Streak Protection
- [ ] "Streak Freeze" power-up (earned or purchased)
- [ ] Grace period: Streak doesn't break until 48 hours of inactivity

---

## 6. Social Features

### Share Enhancements
- [ ] Animated deal card for Twitter/social
- [ ] Include achievement badges on share card
- [ ] "Challenge a friend" - send pitch challenge link
- [ ] Referral bonus: +200 XP when friend completes first pitch

### Social Proof
- [ ] Show "X people pitching right now" on landing page
- [ ] Recent deals ticker on landing page
- [ ] "Your friend [name] just closed a deal!" notifications

---

## 7. Seasonal Events

### Event Ideas
- [ ] **Shark Week** - 2x XP for all pitches
- [ ] **Black Friday** - Special "investor frenzy" mode with faster offers
- [ ] **New Year Challenge** - Pitch your "2025 startup idea"
- [ ] **Founder's Day** - Community challenge, collective deal goal

---

## 8. Power-Ups / Consumables

### Types
- [ ] **Confidence Boost** - Start with +10 confidence on all sharks
- [ ] **Mulligan** - Redo your last answer
- [ ] **Insider Info** - See one shark's exact concerns before Q&A
- [ ] **Extra Time** - Add 2 minutes to negotiation phase

### Earning Power-Ups
- [ ] Daily login rewards
- [ ] Achievement rewards
- [ ] Level up rewards
- [ ] Purchase with in-app currency

---

## 9. In-App Currency

### Currency: "Shark Coins"
- [ ] Earn from achievements, daily challenges, streaks
- [ ] Spend on power-ups, cosmetics
- [ ] Optional: Purchase with real money

### Cosmetics
- [ ] Custom pitch backgrounds
- [ ] Animated deal card themes
- [ ] Profile badges and borders
- [ ] Shark "skins" (different investor characters)

---

## 10. Progress Tracking

### Pitch Analytics Dashboard
- [ ] Total pitches given
- [ ] Deal success rate
- [ ] Average valuation achieved
- [ ] Favorite shark (who gives you most offers)
- [ ] Weakest area (what causes sharks to go out)

### Improvement Tips
- [ ] AI-generated feedback after each pitch
- [ ] "You lost Kevin when you mentioned X"
- [ ] "Try emphasizing Y next time"

---

## Implementation Priority

### Phase 1 (MVP)
1. Achievement system (basic badges)
2. XP & Levels
3. Enhanced leaderboard (weekly + all-time)

### Phase 2
4. Daily challenges
5. Pitch streaks
6. Share enhancements

### Phase 3
7. Power-ups
8. Social features
9. Seasonal events

### Phase 4
10. In-app currency
11. Cosmetics shop
12. Advanced analytics

---

## Technical Notes

### Database Schema (Firestore)
```javascript
users/{uid}/gamification: {
  xp: number,
  level: number,
  achievements: string[],
  streak: {
    current: number,
    lastPitchDate: timestamp,
    longest: number
  },
  stats: {
    totalPitches: number,
    totalDeals: number,
    totalOffers: number,
    bestValuation: number
  },
  dailyChallenges: {
    date: string,
    challenges: [...],
    completed: [...]
  }
}
```

### Events to Track
- pitch_started
- pitch_ended
- offer_received
- deal_closed
- shark_out
- counter_offer_made
- bidding_war_started
- achievement_unlocked
- level_up
