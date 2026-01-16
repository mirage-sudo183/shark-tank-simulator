/**
 * Shark Tank Simulator
 * Entry form → Transition → Live investor panel
 * With AI-powered shark responses via SSE
 */

(function() {
  'use strict';

  // ========================================
  // Configuration
  // ========================================
  // Detect production (Vercel) vs local development
  const isProduction = window.location.hostname.includes('vercel.app') ||
                       window.location.hostname === 'sharktanksimulator.com' ||
                       (!window.location.hostname.includes('localhost') && window.location.port === '');

  // Railway backend URL for production, local Flask server for development
  const RAILWAY_BACKEND_URL = 'https://shark-tank-simulator-production-bbd8.up.railway.app';
  const API_BASE = isProduction ? RAILWAY_BACKEND_URL : window.location.origin;

  const TOTAL_SESSION_TIME = 900; // 15 minutes total
  const PITCH_DURATION = 60; // 1 minute max for pitch
  const USE_SSE = isProduction || window.location.port === '8443'; // Use SSE for Railway and local Flask

  // ========================================
  // State
  // ========================================
  const STATES = ['live', 'interested', 'out'];
  const PHASES = ['pitch', 'qa', 'offers', 'closed'];
  let pitchData = null;
  let timerInterval = null;
  let remainingSeconds = TOTAL_SESSION_TIME;
  let pitchTimeRemaining = PITCH_DURATION;
  let mediaStream = null;
  let recognition = null;
  let transcript = [];
  let isListening = false;
  let currentPhase = 'pitch';
  let sessionId = null;
  let eventSource = null;
  let sharkStates = {};
  let pendingOffers = [];

  // TTS Audio Player
  let audioPlayer = null;
  let audioQueue = [];
  let isPlayingAudio = false;

  // Message deduplication
  let lastMessageIds = new Set();

  // Demo mode flag
  let isDemoMode = false;

  // ========================================
  // Credits System
  // ========================================
  const INITIAL_CREDITS = 5.00; // $5 in free credits
  const COST_PER_PITCH = 0.50; // ~$0.50 per pitch session
  const CREDITS_STORAGE_KEY = 'shark_tank_credits';

  function getCredits() {
    const stored = localStorage.getItem(CREDITS_STORAGE_KEY);
    if (stored === null) {
      // First time user - give them initial credits
      setCredits(INITIAL_CREDITS);
      return INITIAL_CREDITS;
    }
    return parseFloat(stored);
  }

  function setCredits(amount) {
    localStorage.setItem(CREDITS_STORAGE_KEY, amount.toFixed(2));
    updateCreditsDisplay();
  }

  function deductCredits(amount = COST_PER_PITCH) {
    const current = getCredits();
    const newAmount = Math.max(0, current - amount);
    setCredits(newAmount);
    return newAmount;
  }

  function hasCredits() {
    return getCredits() > 0;
  }

  function updateCreditsDisplay() {
    const credits = getCredits();
    const formattedCredits = `$${credits.toFixed(2)}`;

    // Update all credit displays
    const creditsAmount = document.getElementById('creditsAmount');
    const panelCreditsAmount = document.getElementById('panelCreditsAmount');

    if (creditsAmount) creditsAmount.textContent = formattedCredits;
    if (panelCreditsAmount) panelCreditsAmount.textContent = formattedCredits;

    // Update styling based on credit level
    const creditsBar = document.getElementById('creditsBar');
    const creditsBanner = document.getElementById('creditsBanner');

    const elements = [creditsBar, creditsBanner].filter(Boolean);
    elements.forEach(el => {
      el.classList.remove('credits-low', 'credits-critical');
      if (credits <= 1) {
        el.classList.add('credits-critical');
      } else if (credits <= 2) {
        el.classList.add('credits-low');
      }
    });
  }

  function showCreditsUI() {
    if (!isGuest) return; // Only show for guests

    const creditsBar = document.getElementById('creditsBar');
    const creditsBanner = document.getElementById('creditsBanner');

    if (creditsBar) creditsBar.style.display = 'flex';
    if (creditsBanner) creditsBanner.style.display = 'block';

    updateCreditsDisplay();
  }

  function hideCreditsUI() {
    const creditsBar = document.getElementById('creditsBar');
    const creditsBanner = document.getElementById('creditsBanner');

    if (creditsBar) creditsBar.style.display = 'none';
    if (creditsBanner) creditsBanner.style.display = 'none';
  }

  function showCreditsExhaustedModal() {
    const modal = document.getElementById('creditsExhaustedModal');
    if (modal) modal.style.display = 'flex';
  }

  window.hideCreditsModal = function() {
    const modal = document.getElementById('creditsExhaustedModal');
    if (modal) modal.style.display = 'none';
  };

  function initCreditsSystem() {
    // Upgrade buttons
    const upgradeBtn = document.getElementById('creditsUpgradeBtn');
    const panelUpgradeBtn = document.getElementById('panelUpgradeBtn');
    const modalTwitterBtn = document.getElementById('modalTwitterLoginBtn');

    const handleUpgrade = () => {
      if (window.firebaseAuth) {
        window.firebaseAuth.signInWithTwitter().catch(err => {
          console.log('Twitter login failed:', err);
        });
      } else {
        showView('authView');
      }
    };

    if (upgradeBtn) upgradeBtn.addEventListener('click', handleUpgrade);
    if (panelUpgradeBtn) panelUpgradeBtn.addEventListener('click', handleUpgrade);
    if (modalTwitterBtn) modalTwitterBtn.addEventListener('click', handleUpgrade);
  }

  // ========================================
  // Demo Mode Script (Pre-defined pitch for guests)
  // ========================================
  const DEMO_SCRIPT = {
    pitchData: {
      companyName: "FreshBite",
      amountRaising: 500000,
      equityPercent: 10,
      companyDescription: "A meal kit delivery service that uses AI to personalize recipes based on your dietary preferences and what's already in your fridge.",
      proofType: 'customers',
      proofValue: '2,500 active subscribers'
    },
    conversation: [
      // Initial reactions after "pitch" phase
      { delay: 3000, shark: "marcus_kellan", type: "thinking" },
      { delay: 4500, shark: "marcus_kellan", type: "message", text: "I love the concept. How do you handle the logistics of ingredient sourcing? That's usually where meal kit companies struggle." },
      { delay: 8000, shark: "elena_brooks", type: "message", text: "The AI personalization angle is interesting. What's your customer acquisition cost, and how long does it take to recoup that?" },
      { delay: 12000, shark: "victor_slate", type: "thinking" },
      { delay: 14000, shark: "victor_slate", type: "message", text: "I've seen a lot of meal kit companies come and go. The churn in this industry is brutal. What's your retention rate after 6 months?" },
      { delay: 18000, shark: "daniel_frost", type: "message", text: "I'm curious about your technology moat. What stops HelloFresh from just copying your AI feature tomorrow?" },
      // Victor goes out
      { delay: 23000, shark: "victor_slate", type: "message", text: "Look, I appreciate the hustle, but this market is just too crowded for my taste. I'm out." },
      { delay: 24000, shark: "victor_slate", type: "out" },
      // Richard shows interest
      { delay: 28000, shark: "richard_hale", type: "message", text: "I actually like this. The fridge integration is clever - it reduces waste and increases convenience. That's a real differentiator." },
      // Elena makes an offer
      { delay: 33000, shark: "elena_brooks", type: "message", text: "You know what? I'm going to take a chance here. I'll give you the $500,000, but I want 20% equity." },
      { delay: 34000, shark: "elena_brooks", type: "offer", amount: 500000, equity: 20 },
      // Demo ends
      { delay: 40000, type: "demo_end" }
    ]
  };

  // Shark name mapping for demo
  const SHARK_NAMES = {
    'mark_cuban': 'Mark Cuban',
    'lori_greiner': 'Lori Greiner',
    'kevin_oleary': 'Kevin O\'Leary',
    'robert_herjavec': 'Robert Herjavec',
    'richard_branson': 'Richard Branson'
  };

  // ========================================
  // Auth State
  // ========================================
  let currentUser = null;
  let isGuest = false;
  let firebaseReady = false;

  function initAuth() {
    // Set up button listeners immediately (don't wait for Firebase)
    setupAuthButtons();

    // Wait for Firebase to be ready for auth state changes
    if (window.firebaseAuth) {
      setupFirebaseAuthListeners();
    } else {
      window.addEventListener('firebase-ready', setupFirebaseAuthListeners);
    }
  }

  function setupFirebaseAuthListeners() {
    firebaseReady = true;

    if (!window.firebaseAuth || !window.firebaseAuth.onAuthStateChanged) {
      console.log('Firebase auth not available');
      return;
    }

    // Listen for auth state changes
    window.firebaseAuth.onAuthStateChanged((user) => {
      currentUser = user;
      updateAuthUI();

      // If user just logged in and we're on auth view, go to entry form
      if (user && document.getElementById('authView').style.display !== 'none') {
        showView('entryView');
      }
    });
  }

  function setupAuthButtons() {
    // Twitter login button
    const twitterLoginBtn = document.getElementById('twitterLoginBtn');
    if (twitterLoginBtn) {
      twitterLoginBtn.addEventListener('click', async () => {
        if (!window.firebaseAuth || !window.firebaseAuth.signInWithTwitter) {
          alert('Twitter sign-in is not available. Please try the free trial instead.');
          return;
        }
        try {
          twitterLoginBtn.disabled = true;
          twitterLoginBtn.textContent = 'Signing in...';
          await window.firebaseAuth.signInWithTwitter();
          // onAuthStateChanged will handle the redirect
        } catch (error) {
          console.error('Twitter login failed:', error);
          alert('Sign in failed. Please try again.');
          twitterLoginBtn.disabled = false;
          twitterLoginBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            Sign in with X (Twitter)
          `;
        }
      });
    }

    // Guest button
    const guestBtn = document.getElementById('guestBtn');
    if (guestBtn) {
      guestBtn.addEventListener('click', () => {
        // Check if guest has credits
        if (!hasCredits()) {
          showCreditsExhaustedModal();
          return;
        }
        isGuest = true;
        currentUser = null;
        showView('entryView');
        showCreditsUI();
        updateAuthUI();
      });
    }

    // Logout button (entry view)
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        try {
          if (window.firebaseAuth) {
            await window.firebaseAuth.signOutUser();
          }
          currentUser = null;
          isGuest = false;
          hideCreditsUI();
          updateAuthUI();
          showView('authView');
        } catch (error) {
          console.error('Logout failed:', error);
        }
      });
    }

    // Logout button (auth view)
    const authLogoutBtn = document.getElementById('authLogoutBtn');
    if (authLogoutBtn) {
      authLogoutBtn.addEventListener('click', async () => {
        try {
          await window.firebaseAuth.signOutUser();
          currentUser = null;
          isGuest = false;
          updateAuthUI();
        } catch (error) {
          console.error('Logout failed:', error);
        }
      });
    }

    // Continue to form button (auth view when logged in)
    const continueToFormBtn = document.getElementById('continueToFormBtn');
    if (continueToFormBtn) {
      continueToFormBtn.addEventListener('click', () => {
        showView('entryView');
      });
    }

    // Leaderboard buttons
    const viewLeaderboardBtn = document.getElementById('viewLeaderboardBtn');
    if (viewLeaderboardBtn) {
      viewLeaderboardBtn.addEventListener('click', () => showLeaderboard());
    }

    const userLeaderboardBtn = document.getElementById('userLeaderboardBtn');
    if (userLeaderboardBtn) {
      userLeaderboardBtn.addEventListener('click', () => showLeaderboard());
    }

    const leaderboardBackBtn = document.getElementById('leaderboardBackBtn');
    if (leaderboardBackBtn) {
      leaderboardBackBtn.addEventListener('click', () => {
        // NO-LOGIN VERSION: Always go to entry view
        showView('entryView');
      });
    }

    // Back to Auth button
    const backToAuthBtn = document.getElementById('backToAuthBtn');
    if (backToAuthBtn) {
      backToAuthBtn.addEventListener('click', async () => {
        // If logged in, sign out first
        if (currentUser && window.firebaseAuth) {
          await window.firebaseAuth.signOutUser();
          currentUser = null;
        }
        isGuest = false;
        hideCreditsUI();
        showView('authView');
      });
    }

    // Leaderboard tabs
    document.querySelectorAll('.leaderboard-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.leaderboard-tab').forEach(t => t.classList.remove('leaderboard-tab--active'));
        tab.classList.add('leaderboard-tab--active');
        loadLeaderboard(tab.dataset.tab);
      });
    });
  }

  function updateAuthUI() {
    const userBar = document.getElementById('userBar');
    const userBarAvatar = document.getElementById('userBarAvatar');
    const userBarName = document.getElementById('userBarName');

    // Auth view elements
    const authLoginContent = document.getElementById('authLoginContent');
    const authLoggedInContent = document.getElementById('authLoggedInContent');
    const authUserAvatar = document.getElementById('authUserAvatar');
    const authUserName = document.getElementById('authUserName');

    if (currentUser) {
      // Entry view user bar
      if (userBar) {
        userBar.style.display = 'flex';
        if (userBarAvatar) {
          userBarAvatar.src = currentUser.photoURL || 'https://via.placeholder.com/32';
        }
        if (userBarName) {
          userBarName.textContent = currentUser.twitterHandle ? `@${currentUser.twitterHandle}` : currentUser.displayName;
        }
      }

      // Auth view logged-in state
      if (authLoginContent) authLoginContent.style.display = 'none';
      if (authLoggedInContent) {
        authLoggedInContent.style.display = 'flex';
        if (authUserAvatar) {
          authUserAvatar.src = currentUser.photoURL || 'https://via.placeholder.com/48';
        }
        if (authUserName) {
          authUserName.textContent = currentUser.twitterHandle ? `@${currentUser.twitterHandle}` : currentUser.displayName;
        }
      }
    } else {
      // Not logged in
      if (userBar) userBar.style.display = 'none';
      if (authLoginContent) authLoginContent.style.display = 'block';
      if (authLoggedInContent) authLoggedInContent.style.display = 'none';

      // Reset Twitter login button to original state
      const twitterLoginBtn = document.getElementById('twitterLoginBtn');
      if (twitterLoginBtn) {
        twitterLoginBtn.disabled = false;
        twitterLoginBtn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
          </svg>
          Sign in with X (Twitter)
        `;
      }
    }

    // Update leaderboard user card
    updateLeaderboardUserCard();
  }

  // ========================================
  // Leaderboard
  // ========================================
  async function showLeaderboard() {
    showView('leaderboardView');
    await loadLeaderboard('verified');
  }

  async function loadLeaderboard(type = 'verified') {
    const listContainer = document.getElementById('leaderboardList');
    if (!listContainer) return;

    // Show loading
    listContainer.innerHTML = `
      <div class="leaderboard-loading">
        <div class="loading-spinner"></div>
        Loading leaderboard...
      </div>
    `;

    try {
      if (!window.firebaseAuth) {
        throw new Error('Firebase not ready');
      }

      const entries = await window.firebaseAuth.getLeaderboard(type, 50);

      if (entries.length === 0) {
        listContainer.innerHTML = `
          <div class="leaderboard-empty">
            <p>No pitches yet. Be the first!</p>
          </div>
        `;
        return;
      }

      listContainer.innerHTML = entries.map((entry, index) => {
        const pitch = entry.pitchData || {};
        const outcome = entry.outcome || {};
        const verification = entry.verification || {};
        const metrics = verification.metrics || {};
        const protocol = verification.protocol || {};

        // Format the deal terms comparison
        const askAmount = pitch.amountRaising ? `$${formatNumber(pitch.amountRaising)}` : '';
        const askEquity = pitch.equityPercent ? `${pitch.equityPercent}%` : '';
        const gotAmount = outcome.dealAmount ? `$${formatNumber(outcome.dealAmount)}` : '';
        const gotEquity = outcome.dealEquity ? `${outcome.dealEquity}%` : '';

        // Format verification metrics
        let metricsDisplay = '';
        if (metrics.primaryLabel && metrics.primaryValue) {
          metricsDisplay = `${metrics.primaryLabel}: $${formatNumber(metrics.primaryValue)}`;
        }

        // Truncate description
        const description = pitch.description || pitch.companyDescription || '';
        const shortDesc = description.length > 80 ? description.substring(0, 80) + '...' : description;

        // Get logo from verification (DefiLlama or TrustMRR)
        const logoUrl = protocol.logo || verification.logo || null;

        return `
        <div class="leaderboard-entry ${index < 3 ? 'leaderboard-entry--top' : ''}">
          <div class="entry-header">
            <span class="entry-rank">#${entry.rank}</span>
            ${logoUrl ? `
              <img src="${logoUrl}" alt="${pitch.companyName || 'Protocol'}" class="entry-logo" onerror="this.style.display='none'">
            ` : ''}
            <span class="entry-name">${entry.userTwitterHandle || '@anonymous'}</span>
            <div class="entry-deal-amount">
              <span class="entry-amount">$${formatNumber(outcome.dealAmount || 0)}</span>
              ${verification.type !== 'unverified' ? `
                <span class="entry-verified" title="${verification.level || 'Verified'}">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                </span>
              ` : ''}
            </div>
          </div>
          <div class="entry-details">
            <span class="entry-company">${pitch.companyName || 'Unknown'}</span>
            ${shortDesc ? `<span class="entry-description">"${shortDesc}"</span>` : ''}
            ${askAmount && gotAmount ? `
              <span class="entry-terms">Asked: ${askAmount} for ${askEquity} → Got: ${gotAmount} for ${gotEquity}</span>
            ` : ''}
            <div class="entry-meta">
              ${outcome.shark ? `<span class="entry-shark">Shark: ${outcome.shark}</span>` : ''}
              ${metricsDisplay ? `<span class="entry-metrics">${metricsDisplay}</span>` : ''}
            </div>
          </div>
        </div>
      `}).join('');

    } catch (error) {
      console.error('Failed to load leaderboard:', error);
      listContainer.innerHTML = `
        <div class="leaderboard-empty">
          <p>Failed to load leaderboard. Please try again.</p>
        </div>
      `;
    }
  }

  async function updateLeaderboardUserCard() {
    const card = document.getElementById('leaderboardUserCard');
    if (!card || !currentUser) {
      if (card) card.style.display = 'none';
      return;
    }

    try {
      const bestPitch = await window.firebaseAuth.getUserBestPitch(currentUser.uid);

      if (bestPitch) {
        card.style.display = 'flex';
        document.getElementById('userCardAvatar').src = currentUser.photoURL || 'https://via.placeholder.com/40';
        document.getElementById('userCardName').textContent = `@${currentUser.twitterHandle || currentUser.displayName}`;
        document.getElementById('userCardCompany').textContent = bestPitch.pitchData?.companyName || 'Unknown';
        document.getElementById('userCardAmount').textContent = `$${formatNumber(bestPitch.outcome?.dealAmount || 0)}`;
      } else {
        card.style.display = 'flex';
        document.getElementById('userCardAvatar').src = currentUser.photoURL || 'https://via.placeholder.com/40';
        document.getElementById('userCardName').textContent = `@${currentUser.twitterHandle || currentUser.displayName}`;
        document.getElementById('userCardCompany').textContent = 'No deals yet';
        document.getElementById('userCardAmount').textContent = '$0';
        document.getElementById('userCardRank').textContent = '--';
      }
    } catch (error) {
      card.style.display = 'none';
    }
  }

  function formatNumber(num) {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(0) + 'K';
    }
    return num.toString();
  }

  // ========================================
  // View Management
  // ========================================
  function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.style.display = 'none');
    const view = document.getElementById(viewId);
    if (view) view.style.display = 'flex';

    // Update auth UI when switching views (ensures user bar is visible)
    updateAuthUI();
  }

  // ========================================
  // Verification
  // ========================================
  let currentVerification = null;
  let defiSearchTimeout = null;

  function updateVerificationUI(proofType) {
    const verificationSection = document.getElementById('verificationSection');
    if (!verificationSection) return;

    // Only show verification for logged-in users with revenue or users proof
    if (currentUser && (proofType === 'revenue' || proofType === 'users')) {
      verificationSection.style.display = 'block';
    } else {
      verificationSection.style.display = 'none';
    }
  }

  function initVerification() {
    // DefiLlama verification
    const verifyDefiBtn = document.getElementById('verifyDefiBtn');
    const defiModal = document.getElementById('defiModal');
    const closeDefiModal = document.getElementById('closeDefiModal');
    const defiSearchInput = document.getElementById('defiSearchInput');
    const defiSearchResults = document.getElementById('defiSearchResults');
    const defiSearchSpinner = document.getElementById('defiSearchSpinner');

    if (verifyDefiBtn && defiModal) {
      verifyDefiBtn.addEventListener('click', () => {
        defiModal.style.display = 'flex';
        defiSearchInput.value = '';
        defiSearchResults.innerHTML = '';
        defiSearchInput.focus();
      });

      closeDefiModal.addEventListener('click', () => {
        defiModal.style.display = 'none';
      });

      defiModal.addEventListener('click', (e) => {
        if (e.target === defiModal) {
          defiModal.style.display = 'none';
        }
      });

      // Search with debounce
      defiSearchInput.addEventListener('input', () => {
        clearTimeout(defiSearchTimeout);
        const query = defiSearchInput.value.trim();

        if (query.length < 2) {
          defiSearchResults.innerHTML = '';
          return;
        }

        defiSearchSpinner.style.display = 'block';

        defiSearchTimeout = setTimeout(async () => {
          try {
            const response = await fetch(`${API_BASE}/api/verify/defi/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            defiSearchSpinner.style.display = 'none';

            if (data.results && data.results.length > 0) {
              defiSearchResults.innerHTML = data.results.map(protocol => `
                <div class="search-result-item" data-slug="${protocol.id}">
                  <img class="search-result-logo" src="${protocol.logo || 'https://via.placeholder.com/36'}" alt="${protocol.name}">
                  <div class="search-result-info">
                    <span class="search-result-name">${protocol.name}</span>
                    <span class="search-result-meta">${protocol.category || ''} ${protocol.twitter ? '• @' + protocol.twitter : ''}</span>
                  </div>
                  <span class="search-result-tvl">${formatTVL(protocol.tvl)}</span>
                </div>
              `).join('');

              // Add click handlers
              defiSearchResults.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => verifyDefiProtocol(item.dataset.slug));
              });
            } else {
              defiSearchResults.innerHTML = '<p style="color: #71717a; text-align: center;">No protocols found</p>';
            }
          } catch (error) {
            console.error('DeFi search error:', error);
            defiSearchSpinner.style.display = 'none';
            defiSearchResults.innerHTML = '<p style="color: #ef4444; text-align: center;">Search failed</p>';
          }
        }, 300);
      });
    }

    // TrustMRR verification
    const verifyTrustMRRBtn = document.getElementById('verifyTrustMRRBtn');
    const trustmrrModal = document.getElementById('trustmrrModal');
    const closeTrustMRRModal = document.getElementById('closeTrustMRRModal');
    const trustmrrUrlInput = document.getElementById('trustmrrUrlInput');
    const verifyTrustMRRSubmit = document.getElementById('verifyTrustMRRSubmit');
    const trustmrrResult = document.getElementById('trustmrrResult');

    if (verifyTrustMRRBtn && trustmrrModal) {
      verifyTrustMRRBtn.addEventListener('click', () => {
        trustmrrModal.style.display = 'flex';
        trustmrrUrlInput.value = '';
        trustmrrResult.style.display = 'none';
        trustmrrUrlInput.focus();
      });

      closeTrustMRRModal.addEventListener('click', () => {
        trustmrrModal.style.display = 'none';
      });

      trustmrrModal.addEventListener('click', (e) => {
        if (e.target === trustmrrModal) {
          trustmrrModal.style.display = 'none';
        }
      });

      verifyTrustMRRSubmit.addEventListener('click', () => verifyTrustMRRProfile());
    }
  }

  async function verifyDefiProtocol(protocolSlug) {
    const defiModal = document.getElementById('defiModal');
    const verificationStatus = document.getElementById('verificationStatus');
    const verificationText = document.getElementById('verificationText');
    const verificationDetails = document.getElementById('verificationDetails');

    try {
      const token = await window.firebaseAuth.getIdToken();
      const response = await fetch(`${API_BASE}/api/verify/defi`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ protocolSlug })
      });

      const result = await response.json();

      defiModal.style.display = 'none';

      // Handle different verification levels
      const level = result.level;

      if (level === 'verified' || level === 'followed' || level === 'claimed') {
        currentVerification = {
          type: 'defi',
          source: 'defillama',
          ...result
        };

        // Set verification badge based on level
        let badgeText = '';
        let badgeClass = '';

        if (level === 'verified') {
          badgeText = '✅ Verified via DefiLlama';
          badgeClass = 'verification-verified';
        } else if (level === 'followed') {
          badgeText = '🔗 Team Verified via DefiLlama';
          badgeClass = 'verification-followed';
        } else {
          badgeText = '⚠️ Claimed (Unverified)';
          badgeClass = 'verification-claimed';
        }

        // Display primary metric (fees first, then TVL)
        const metrics = result.metrics || {};
        let metricDisplay = '';
        if (metrics.primaryLabel && metrics.primaryValue > 0) {
          metricDisplay = `${metrics.primaryLabel}: ${formatTVL(metrics.primaryValue)}`;
        } else if (metrics.tvl > 0) {
          metricDisplay = `TVL: ${formatTVL(metrics.tvl)}`;
        }

        verificationText.textContent = badgeText;
        verificationDetails.textContent = `${result.protocol?.name}${metricDisplay ? ' • ' + metricDisplay : ''}`;
        verificationStatus.style.display = 'flex';
        verificationStatus.className = `verification-status ${badgeClass}`;

        // Hide verification options
        document.querySelector('.verification-options').style.display = 'none';

        // Show confirmation message
        if (level === 'claimed') {
          alert(`${result.message}\n\nYour pitch will appear in the Unverified leaderboard.`);
        } else {
          alert(`${result.message}\n\nYour pitch will appear in the Verified leaderboard!`);
        }
      } else if (level === 'no_metrics') {
        // Protocol exists but has no revenue/TVL - cannot claim
        alert(`${result.message}\n\nPlease select a protocol with verifiable fees or TVL data.`);
      } else {
        alert(result.message || 'Verification failed. Protocol not found.');
      }
    } catch (error) {
      console.error('DeFi verification error:', error);
      alert('Verification failed. Please try again.');
    }
  }

  async function verifyTrustMRRProfile() {
    const trustmrrModal = document.getElementById('trustmrrModal');
    const trustmrrUrlInput = document.getElementById('trustmrrUrlInput');
    const trustmrrResult = document.getElementById('trustmrrResult');
    const verificationStatus = document.getElementById('verificationStatus');
    const verificationText = document.getElementById('verificationText');
    const verificationDetails = document.getElementById('verificationDetails');

    const profileUrl = trustmrrUrlInput.value.trim();
    if (!profileUrl) {
      trustmrrResult.textContent = 'Please enter a TrustMRR profile URL';
      trustmrrResult.className = 'verification-result error';
      trustmrrResult.style.display = 'block';
      return;
    }

    try {
      const token = await window.firebaseAuth.getIdToken();
      const response = await fetch(`${API_BASE}/api/verify/trustmrr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ profileUrl })
      });

      const result = await response.json();

      if (result.verified) {
        currentVerification = {
          type: 'trustmrr',
          source: 'trustmrr',
          ...result
        };
        trustmrrModal.style.display = 'none';
        verificationText.textContent = 'Verified via TrustMRR';
        verificationDetails.textContent = `${result.profile?.company_name || 'Company'} • MRR: ${result.metrics?.mrr_display || formatMRR(result.metrics?.mrr)}`;
        verificationStatus.style.display = 'flex';

        // Hide verification options
        document.querySelector('.verification-options').style.display = 'none';
      } else {
        trustmrrResult.textContent = result.message || 'Verification failed';
        trustmrrResult.className = `verification-result ${result.level === 'not_found' ? 'error' : 'warning'}`;
        trustmrrResult.style.display = 'block';
      }
    } catch (error) {
      console.error('TrustMRR verification error:', error);
      trustmrrResult.textContent = 'Verification failed. Please try again.';
      trustmrrResult.className = 'verification-result error';
      trustmrrResult.style.display = 'block';
    }
  }

  function formatTVL(tvl) {
    if (!tvl || typeof tvl !== 'number') return '$0';
    if (tvl >= 1e9) return `$${(tvl / 1e9).toFixed(2)}B`;
    if (tvl >= 1e6) return `$${(tvl / 1e6).toFixed(2)}M`;
    if (tvl >= 1e3) return `$${(tvl / 1e3).toFixed(1)}K`;
    return `$${Math.round(tvl)}`;
  }

  function formatMRR(mrr) {
    if (!mrr) return '$0';
    if (mrr >= 1e6) return `$${(mrr / 1e6).toFixed(2)}M`;
    if (mrr >= 1e3) return `$${(mrr / 1e3).toFixed(1)}K`;
    return `$${mrr.toFixed(0)}`;
  }

  // ========================================
  // Entry Form
  // ========================================
  function initEntryForm() {
    const form = document.getElementById('entryForm');
    const proofType = document.getElementById('proofType');
    const proofValueGroup = document.getElementById('proofValueGroup');
    const proofValueLabel = document.getElementById('proofValueLabel');
    const proofValuePrefix = document.getElementById('proofValuePrefix');
    const proofValue = document.getElementById('proofValue');
    const descTextarea = document.getElementById('companyDescription');
    const descCharCount = document.getElementById('descCharCount');
    const whyNowTextarea = document.getElementById('whyNow');
    const whyNowCharCount = document.getElementById('whyNowCharCount');

    if (!form) return;

    // Character count for description
    if (descTextarea && descCharCount) {
      descTextarea.addEventListener('input', () => {
        descCharCount.textContent = descTextarea.value.length;
      });
    }

    // Character count for why now
    if (whyNowTextarea && whyNowCharCount) {
      whyNowTextarea.addEventListener('input', () => {
        whyNowCharCount.textContent = whyNowTextarea.value.length;
      });
    }

    // Proof type conditional field
    if (proofType && proofValueGroup) {
      proofType.addEventListener('change', () => {
        const value = proofType.value;

        if (value === 'idea') {
          proofValueGroup.style.display = 'none';
          proofValue.removeAttribute('required');
        } else {
          proofValueGroup.style.display = 'flex';
          proofValue.setAttribute('required', '');

          // Update label and prefix based on type
          switch (value) {
            case 'revenue':
              proofValueLabel.textContent = 'Monthly revenue (MRR)';
              proofValuePrefix.textContent = '$';
              proofValue.placeholder = '25000';
              break;
            case 'users':
              proofValueLabel.textContent = 'Active users';
              proofValuePrefix.textContent = '';
              proofValue.placeholder = '5000';
              break;
            case 'customers':
              proofValueLabel.textContent = 'Signed customers';
              proofValuePrefix.textContent = '';
              proofValue.placeholder = '12';
              break;
          }
        }

        // Show verification section for logged in users with revenue/users
        updateVerificationUI(value);
      });
    }

    // Initialize verification UI
    initVerification();

    // Form submission
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Check credits for guests
      if (isGuest) {
        if (!hasCredits()) {
          showCreditsExhaustedModal();
          return;
        }
        // Deduct credits for this pitch
        deductCredits();
      }

      // Collect form data
      pitchData = {
        companyName: form.companyName.value,
        amountRaising: parseInt(form.amountRaising.value),
        equityPercent: parseInt(form.equityPercent.value),
        companyDescription: form.companyDescription.value,
        whyNow: form.whyNow.value,
        proofType: form.proofType.value,
        proofValue: form.proofValue?.value || null,
        expectedPushback: form.expectedPushback?.value || null
      };

      // Store for later use (including verification)
      window.pitchData = pitchData;
      window.pitchVerification = currentVerification;

      // Show transition
      showView('transitionView');

      // NO-LOGIN VERSION: Everyone gets real AI sharks (no demo mode)
      isDemoMode = false;

      // Build headers with auth token if available
      const headers = { 'Content-Type': 'application/json' };
      if (currentUser && window.firebaseAuth) {
        try {
          const token = await window.firebaseAuth.getIdToken();
          if (token) headers['Authorization'] = `Bearer ${token}`;
        } catch (e) {
          console.log('Could not get auth token');
        }
      }

      // Start session with backend
      try {
        const response = await fetch(`${API_BASE}/api/session/start`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ pitchData, verification: currentVerification })
        });

        if (response.ok) {
          const data = await response.json();
          sessionId = data.sessionId;
          sharkStates = {};
          data.sharks.forEach(shark => {
            sharkStates[shark.id] = shark;
          });
          console.log('Session started:', sessionId);
        }
      } catch (err) {
        console.log('Backend not available, running in offline mode');
      }

      // After transition, show panel
      setTimeout(() => {
        showView('panelView');
        initPanel();
      }, 2500);
    });

    // Skip button (dev/testing) - Quick Test Mode
    const skipBtn = document.getElementById('skipBtn');
    if (skipBtn) {
      skipBtn.addEventListener('click', async () => {
        skipBtn.disabled = true;
        skipBtn.textContent = 'Starting...';

        // Get selected shark from dropdown
        const sharkSelect = document.getElementById('quickTestShark');
        const selectedShark = sharkSelect ? sharkSelect.value : 'victor';

        try {
          // Call the quick test endpoint with selected shark
          const response = await fetch(`${API_BASE}/api/test/quick-session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sharkId: selectedShark })
          });

          const data = await response.json();

          if (data.sessionId) {
            // Set up session data
            sessionId = data.sessionId;
            pitchData = data.pitchData;
            window.pitchData = pitchData;
            currentPhase = 'qa';

            // Initialize shark states from response
            sharkStates = {};
            data.sharks.forEach(shark => {
              sharkStates[shark.id] = {
                ...shark,
                status: shark.status || 'live',
                confidence: shark.confidence || 85
              };
            });

            // Go directly to panel (skip transition)
            showView('panelView');
            initPanelWithSession(data);
          } else {
            throw new Error(data.error || 'Failed to create test session');
          }
        } catch (error) {
          console.error('Quick test failed:', error);
          alert('Quick test failed: ' + error.message);
          skipBtn.disabled = false;
          skipBtn.textContent = '🧪 Test Offer';
        }
      });
    }
  }

  /**
   * Initialize panel with an existing session (for quick test mode)
   */
  function initPanelWithSession(sessionData) {
    console.log('Quick test mode - session:', sessionData.sessionId);

    // Update meeting title
    const meetingTitle = document.getElementById('meetingTitle');
    if (meetingTitle && pitchData) {
      meetingTitle.textContent = `${pitchData.companyName} — Q&A Phase`;
    }

    // Initialize participants (sharks grid)
    initParticipants();

    // Start timer
    remainingSeconds = TOTAL_SESSION_TIME;
    currentPhase = 'qa';
    startTimer();

    // Initialize webcam
    initWebcam();

    // Initialize TTS audio player
    initAudioPlayer();

    // Initialize camera toggle button
    initCameraToggle();

    // Initialize response guidance
    initResponseGuidance();

    // Initialize chat (enable input)
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    if (chatInput) chatInput.disabled = false;
    if (sendBtn) sendBtn.disabled = false;

    // Connect to SSE for real-time events
    connectSSE(sessionData.sessionId);

    // Update phase indicator
    updatePhaseIndicator();

    // Add test mode banner
    const banner = document.createElement('div');
    banner.className = 'test-mode-banner';
    banner.innerHTML = `
      <span>🧪 Quick Test Mode</span>
      <span style="opacity: 0.7; margin-left: 8px;">Offer coming in ~3 seconds...</span>
    `;
    banner.style.cssText = `
      position: fixed;
      top: 10px;
      left: 50%;
      transform: translateX(-50%);
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      padding: 8px 16px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 500;
      z-index: 1000;
      box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
    `;
    document.body.appendChild(banner);

    // Remove banner after 5 seconds
    setTimeout(() => {
      banner.style.opacity = '0';
      banner.style.transition = 'opacity 0.3s';
      setTimeout(() => banner.remove(), 300);
    }, 5000);
  }

  // ========================================
  // Demo Mode Functions (for guests)
  // ========================================

  function initDemoPanel() {
    console.log('Starting demo mode...');

    // Update meeting title with demo company name
    const meetingTitle = document.getElementById('meetingTitle');
    if (meetingTitle && pitchData) {
      meetingTitle.textContent = `${pitchData.companyName} — Demo Mode`;
    }

    // Initialize participants (sharks grid)
    initParticipants();

    // Start timer (just for visual effect)
    remainingSeconds = TOTAL_SESSION_TIME;
    pitchTimeRemaining = PITCH_DURATION;
    currentPhase = 'pitch';
    startTimer();

    // Initialize webcam (still show user's face)
    initWebcam();

    // Initialize TTS audio player
    initAudioPlayer();

    // Show demo mode banner
    showDemoBanner();

    // Disable user inputs (demo is non-interactive)
    disableDemoInputs();

    // Update phase indicator
    updatePhaseIndicator();

    // Start the scripted demo playback
    setTimeout(() => {
      // Auto-transition to Q&A phase after brief pitch display
      currentPhase = 'qa';
      updatePhaseIndicator();
      const meetingTitle = document.getElementById('meetingTitle');
      if (meetingTitle) {
        meetingTitle.textContent = `${pitchData.companyName} — Q&A Phase (Demo)`;
      }
      // Start playing the demo script
      playDemoScript();
    }, 2000);
  }

  function showDemoBanner() {
    const banner = document.getElementById('demoBanner');
    if (banner) {
      banner.style.display = 'flex';
      // Wire up the sign-in button
      const signInBtn = document.getElementById('demoSignInBtn');
      if (signInBtn) {
        signInBtn.onclick = () => {
          // Clean up demo and go to entry
          cleanupDemo();
          showView('entryView'); // NO-LOGIN VERSION
        };
      }
    }
  }

  function hideDemoBanner() {
    const banner = document.getElementById('demoBanner');
    if (banner) {
      banner.style.display = 'none';
    }
  }

  function disableDemoInputs() {
    // Disable mic button
    const micBtn = document.getElementById('micBtn');
    if (micBtn) {
      micBtn.disabled = true;
      micBtn.classList.add('demo-disabled');
      micBtn.title = 'Microphone disabled in demo mode';
    }

    // Disable chat input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.disabled = true;
      chatInput.placeholder = 'Sign in to chat with the sharks!';
    }

    // Disable send button
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.classList.add('demo-disabled');
    }

    // Disable end pitch button
    const endPitchBtn = document.getElementById('endPitchBtn');
    if (endPitchBtn) {
      endPitchBtn.disabled = true;
      endPitchBtn.classList.add('demo-disabled');
    }
  }

  function playDemoScript() {
    const demoTimeouts = [];

    DEMO_SCRIPT.conversation.forEach(event => {
      const timeout = setTimeout(() => {
        if (!isDemoMode) return; // Stop if user left demo

        switch (event.type) {
          case 'thinking':
            showThinking(SHARK_NAMES[event.shark] || event.shark);
            break;

          case 'message':
            hideThinking(SHARK_NAMES[event.shark] || event.shark);
            sendSharkMessage(SHARK_NAMES[event.shark] || event.shark, event.text);
            break;

          case 'out':
            setSharkOut(event.shark, "I'm out.");
            break;

          case 'offer':
            addOfferToUI({
              id: 'demo-offer-' + event.shark,
              sharkId: event.shark,
              sharkName: SHARK_NAMES[event.shark] || event.shark,
              amount: event.amount,
              equity: event.equity,
              isDemo: true
            });
            break;

          case 'demo_end':
            showDemoEndOverlay();
            break;
        }
      }, event.delay);

      demoTimeouts.push(timeout);
    });

    // Store timeouts so we can cancel if user leaves
    window.demoTimeouts = demoTimeouts;
  }

  function showDemoEndOverlay() {
    // Stop the timer
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'demoEndOverlay';
    overlay.className = 'demo-end-overlay';
    overlay.innerHTML = `
      <div class="demo-end-content">
        <div class="demo-end-icon">&#127909;</div>
        <h2>Demo Complete!</h2>
        <p>That was just a preview of what Shark Tank Simulator can do.</p>
        <p>Sign in with Twitter/X to pitch <strong>YOUR</strong> business to the AI sharks!</p>
        <div class="demo-end-buttons">
          <button id="demoEndSignIn" class="demo-end-cta">
            <span>Sign in with</span>
            <span class="x-logo">&#120143;</span>
          </button>
          <button id="demoEndReplay" class="demo-end-secondary">Watch Again</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    // Animate in
    requestAnimationFrame(() => {
      overlay.classList.add('visible');
    });

    // Event handlers
    document.getElementById('demoEndSignIn').onclick = () => {
      cleanupDemo();
      overlay.remove();
      showView('entryView'); // NO-LOGIN VERSION
    };

    document.getElementById('demoEndReplay').onclick = () => {
      overlay.remove();
      cleanupDemo();
      showView('entryView');
    };
  }

  function cleanupDemo() {
    isDemoMode = false;

    // Clear any pending demo timeouts
    if (window.demoTimeouts) {
      window.demoTimeouts.forEach(t => clearTimeout(t));
      window.demoTimeouts = [];
    }

    // Stop timer
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Hide demo banner
    hideDemoBanner();

    // Clear chat
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
      chatMessages.innerHTML = '';
    }

    // Clear offers
    const offersContainer = document.getElementById('offersContainer');
    if (offersContainer) {
      offersContainer.innerHTML = '';
    }
    pendingOffers = [];

    // Reset phase
    currentPhase = 'pitch';
  }

  // ========================================
  // Panel Initialization
  // ========================================
  function initPanel() {
    // Update meeting title with company name
    const meetingTitle = document.getElementById('meetingTitle');
    if (meetingTitle && pitchData) {
      meetingTitle.textContent = `${pitchData.companyName} — Pitch Phase`;
    }

    // Initialize participants
    initParticipants();

    // Start timer: 10-minute session, 3-minute pitch
    remainingSeconds = TOTAL_SESSION_TIME;
    pitchTimeRemaining = PITCH_DURATION;
    currentPhase = 'pitch';
    startTimer();

    // Initialize webcam
    initWebcam();

    // Initialize speech recognition
    initSpeechRecognition();

    // Initialize end pitch button
    initEndPitch();

    // Initialize chat input
    initChatInput();

    // Initialize transcript toggle
    initTranscriptToggle();

    // Initialize offers panel tabs
    initOffersTabs();

    // Initialize TTS audio player
    initAudioPlayer();

    // Initialize camera toggle button
    initCameraToggle();

    // Initialize response guidance
    initResponseGuidance();

    // Connect to SSE if session exists
    if (sessionId) {
      connectSSE();
    }

    // Update phase indicator
    updatePhaseIndicator();
  }

  // ========================================
  // SSE Connection (for local Flask server)
  // ========================================
  function connectSSE() {
    if (!sessionId || !USE_SSE) return;

    eventSource = new EventSource(`${API_BASE}/api/session/${sessionId}/stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleSSEEvent(data);
      } catch (err) {
        console.log('SSE parse error:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.log('SSE connection error, will retry...');
    };
  }

  function disconnectSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  // ========================================
  // Serverless API (for Vercel deployment)
  // ========================================
  let lastShark = '';
  let conversationContext = '';

  async function callServerlessChat(message = null, isInitial = false) {
    if (USE_SSE) return; // Use SSE instead

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: isInitial ? 'initial' : 'message',
          pitchData: pitchData,
          message: message || 'Please give your initial reaction to this pitch.',
          context: conversationContext,
          lastShark: lastShark
        })
      });

      if (response.ok) {
        const data = await response.json();

        // Update tracking
        lastShark = data.sharkId;
        conversationContext += `\n${data.sharkName}: ${data.text}`;

        // Show thinking then message
        showThinking(data.sharkName);
        setTimeout(() => {
          hideThinking(data.sharkName);
          setSpeakingIndicator(data.sharkId, true);
          sendSharkMessage(data.sharkName, data.text);

          // Clear speaking after a delay
          setTimeout(() => {
            setSpeakingIndicator(data.sharkId, false);
          }, 1500);

          // Handle offers
          if (data.offer) {
            addOfferToUI(data.offer);
          }
        }, 1000);
      }
    } catch (err) {
      console.log('Serverless API error:', err);
    }
  }

  function handleSSEEvent(event) {
    console.log('SSE event:', event.type, event);

    switch (event.type) {
      case 'connected':
        console.log('SSE connected to session:', event.sessionId);
        break;

      case 'heartbeat':
        // Keep-alive, no action needed
        break;

      case 'shark_thinking':
        showThinking(event.data.sharkName);
        break;

      case 'shark_speaking':
        // Only set speaking ON here, OFF is handled by audio completion
        if (event.data.speaking) {
          setSpeakingIndicator(event.data.sharkId, true);
        }
        break;

      case 'shark_message':
        // Deduplicate messages
        const msgId = `${event.data.sharkId}-${event.data.text.substring(0, 50)}`;
        if (lastMessageIds.has(msgId)) {
          console.log('Duplicate message ignored:', msgId);
          break;
        }
        lastMessageIds.add(msgId);
        // Keep set from growing too large
        if (lastMessageIds.size > 20) {
          const firstKey = lastMessageIds.values().next().value;
          lastMessageIds.delete(firstKey);
        }

        hideThinking(event.data.sharkName);
        sendSharkMessage(event.data.sharkName, event.data.text);

        // Show response guidance on first shark message
        showResponseGuidance();

        // Play TTS audio if available
        if (event.data.audio || event.data.duration) {
          playSharkAudio(event.data.audio, event.data.sharkId, event.data.duration);
        } else {
          // No audio, clear speaking indicator after a brief delay
          setTimeout(() => {
            setSpeakingIndicator(event.data.sharkId, false);
          }, 500);
        }

        if (event.data.offer) {
          addOfferToUI(event.data.offer);
        }
        break;

      case 'shark_out':
        hideThinking(event.data.sharkName);
        setSharkOut(event.data.sharkId, event.data.message);

        // Check if all sharks are out
        checkAllSharksOut();
        break;

      case 'shark_offer':
        addOfferToUI(event.data.offer);
        break;

      case 'deal_closed':
        showDealClosed(event.data);
        break;

      case 'phase_change':
        currentPhase = event.data.phase;
        updatePhaseIndicator();
        break;

      // New deal flow events
      case 'bidding_war_started':
        showBiddingWarIndicator(event.data);
        break;

      case 'final_offer_countdown':
        showFinalOfferCountdown(event.data);
        break;

      case 'proof_satisfied':
        showProofSatisfied(event.data);
        break;

      case 'deal_recap':
        showDealRecap(event.data);
        break;

      case 'session_complete':
        showSessionComplete(event.data);
        break;

      // NEW: Confidence flag system events
      case 'confidence_update':
        handleConfidenceUpdate(event.data);
        break;

      case 'shark_returned':
        handleSharkReturned(event.data);
        break;

      default:
        console.log('Unknown SSE event type:', event.type);
    }
  }

  // ========================================
  // Confidence Flag System - UI Handlers
  // ========================================
  function handleConfidenceUpdate(data) {
    const { sharkId, sharkName, confidence, delta, flaggedForOffer, flaggedForOut } = data;

    // Update local state
    if (sharkStates[sharkId]) {
      sharkStates[sharkId].confidence = confidence;
      sharkStates[sharkId].flaggedForOffer = flaggedForOffer;
      sharkStates[sharkId].flaggedForOut = flaggedForOut;
    }

    // Update visible confidence bar
    updateConfidenceBar(sharkId, confidence, delta);

    // Show visual confidence change indicator if significant
    if (Math.abs(delta) >= 3) {
      showConfidenceDelta(sharkId, delta);
    }

    console.log(`[Confidence] ${sharkName}: ${confidence} (${delta >= 0 ? '+' : ''}${delta})`);
  }

  function updateConfidenceBar(sharkId, confidence, delta) {
    const bar = document.querySelector(`.confidence-bar[data-investor="${sharkId}"]`);
    if (!bar) return;

    // Update width (confidence is 0-100)
    bar.style.width = `${confidence}%`;

    // Update color class based on confidence level
    bar.classList.remove('low', 'medium', 'high');
    if (confidence < 35) {
      bar.classList.add('low');
    } else if (confidence < 65) {
      bar.classList.add('medium');
    } else {
      bar.classList.add('high');
    }

    // Pulse animation for significant changes
    if (Math.abs(delta) >= 5) {
      bar.classList.add('pulse');
      setTimeout(() => bar.classList.remove('pulse'), 500);
    }
  }

  function showConfidenceDelta(sharkId, delta) {
    const participant = document.querySelector(`[data-investor="${sharkId}"]`);
    if (!participant) return;

    // Create floating indicator
    const indicator = document.createElement('div');
    indicator.className = `confidence-delta ${delta > 0 ? 'positive' : 'negative'}`;
    indicator.textContent = `${delta > 0 ? '+' : ''}${delta}`;

    // Position it over the participant
    participant.style.position = 'relative';
    participant.appendChild(indicator);

    // Animate and remove
    setTimeout(() => {
      indicator.classList.add('fade-out');
      setTimeout(() => indicator.remove(), 300);
    }, 1500);

    // Show shark reaction notification for significant changes
    if (Math.abs(delta) >= 5) {
      showSharkReaction(sharkId, delta);
    }
  }

  // Shark reaction messages based on confidence change
  const SHARK_REACTIONS = {
    marcus: {
      positive: ["I like what I'm hearing!", "This is getting interesting...", "Now we're talking!", "That's a strong point."],
      negative: ["I'm not sure about this...", "That concerns me.", "You're losing me here.", "Hmm, I have doubts."],
      very_positive: ["This could be huge!", "I'm getting excited!", "You've got my attention!"],
      very_negative: ["This doesn't make sense.", "I'm skeptical.", "That's a red flag."]
    },
    victor: {
      positive: ["Show me the money potential.", "The numbers are adding up.", "I can see the ROI.", "That's a royalty opportunity."],
      negative: ["Where's the profit?", "That's not a business, it's a hobby.", "The math doesn't work.", "Too risky."],
      very_positive: ["This is a money machine!", "I smell profit!", "Now THIS is interesting!"],
      very_negative: ["You're out of your mind.", "This is insane.", "No way."]
    },
    elena: {
      positive: ["I can see this on shelves!", "Great product appeal.", "Customers would love this.", "Smart approach."],
      negative: ["It's too complicated.", "Who's the customer?", "I don't see the appeal.", "That's a tough sell."],
      very_positive: ["This is a hero product!", "QVC would eat this up!", "Brilliant!"],
      very_negative: ["I'm losing interest.", "This won't work.", "Not for me."]
    },
    richard: {
      positive: ["Love the vision!", "Bold move.", "That's innovative.", "I see the potential."],
      negative: ["Needs more focus.", "Too ambitious maybe?", "Let's be realistic.", "I'm concerned."],
      very_positive: ["Revolutionary!", "This could change everything!", "Fantastic!"],
      very_negative: ["I'm out.", "Not convinced.", "Can't get behind this."]
    },
    daniel: {
      positive: ["Strong fundamentals.", "Good business sense.", "I appreciate the honesty.", "That's encouraging."],
      negative: ["What about competition?", "The market is tough.", "I have reservations.", "Needs work."],
      very_positive: ["Exceptional!", "You've done the work!", "Very impressive!"],
      very_negative: ["Too many risks.", "I can't invest.", "This worries me."]
    }
  };

  const SHARK_IMAGES = {
    marcus: 'images/sharks/marc_cuban.jpg',
    victor: 'images/sharks/kevin_oleary.jpg',
    elena: 'images/sharks/lori_greiner.jpg',
    richard: 'images/sharks/richard_branson.jpg',
    daniel: 'images/sharks/robert_herjavec.jpg'
  };

  const SHARK_EMOJIS = {
    positive: ['👍', '💪', '🔥', '✨'],
    negative: ['🤔', '😬', '👎', '❌'],
    very_positive: ['🚀', '💰', '🎯', '⭐'],
    very_negative: ['😤', '🙅', '💔', '⚠️']
  };

  function showSharkReaction(sharkId, delta) {
    const container = document.getElementById('sharkReactions');
    if (!container) return;

    const sharkName = SHARK_NAMES[sharkId] || sharkId;
    const reactions = SHARK_REACTIONS[sharkId];
    if (!reactions) return;

    // Determine reaction type
    let reactionType, reactionClass;
    if (delta >= 10) {
      reactionType = 'very_positive';
      reactionClass = 'positive';
    } else if (delta >= 5) {
      reactionType = 'positive';
      reactionClass = 'positive';
    } else if (delta <= -10) {
      reactionType = 'very_negative';
      reactionClass = 'negative';
    } else {
      reactionType = 'negative';
      reactionClass = 'negative';
    }

    const messages = reactions[reactionType] || reactions[reactionClass];
    const message = messages[Math.floor(Math.random() * messages.length)];
    const emojis = SHARK_EMOJIS[reactionType];
    const emoji = emojis[Math.floor(Math.random() * emojis.length)];

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `shark-reaction ${reactionClass}`;
    notification.innerHTML = `
      <div class="shark-reaction-avatar">
        <img src="${SHARK_IMAGES[sharkId]}" alt="${sharkName}">
      </div>
      <div class="shark-reaction-content">
        <div class="shark-reaction-name">${sharkName}</div>
        <div class="shark-reaction-text">${message}</div>
      </div>
      <div class="shark-reaction-emoji">${emoji}</div>
    `;

    container.appendChild(notification);

    // Remove after delay
    setTimeout(() => {
      notification.classList.add('exiting');
      setTimeout(() => notification.remove(), 300);
    }, 3000);

    // Limit to 3 notifications at a time
    while (container.children.length > 3) {
      container.firstChild.remove();
    }
  }

  function handleSharkReturned(data) {
    const { sharkId, sharkName, message, confidence } = data;

    console.log(`[Shark Returned] ${sharkName} is back in the deal!`);

    // Reset shark UI from "out" to "live"
    setSharkReturned(sharkId);

    // Update local state
    if (sharkStates[sharkId]) {
      sharkStates[sharkId].status = 'live';
      sharkStates[sharkId].confidence = confidence;
    }

    // Show message in chat
    sendSharkMessage(sharkName, message);

    // Show notification
    sendSystemMessage(`${sharkName} is back in the deal!`);
  }

  function setSharkReturned(sharkId) {
    const participant = document.querySelector(`[data-investor="${sharkId}"]`);
    if (!participant) return;

    // Reset DOM state attribute
    participant.dataset.state = 'live';

    // Remove "out" visual classes
    const video = participant.querySelector('.participant-video');
    video.classList.remove('participant-video--out');
    participant.classList.remove('participant--out');

    // Reset badge to "LIVE"
    const badge = participant.querySelector('.participant-badge');
    if (badge) {
      badge.classList.remove('badge--out', 'badge--interested');
      badge.classList.add('badge--live');
      badge.textContent = 'LIVE';
    }

    // Add a brief highlight effect
    participant.classList.add('shark-returned');
    setTimeout(() => participant.classList.remove('shark-returned'), 2000);
  }

  // ========================================
  // Speaking Indicator
  // ========================================
  function setSpeakingIndicator(sharkId, speaking) {
    const participant = document.querySelector(`[data-investor="${sharkId}"]`);
    if (!participant) return;

    const video = participant.querySelector('.participant-video');
    if (speaking) {
      video.classList.add('participant-video--speaking');
    } else {
      video.classList.remove('participant-video--speaking');
    }
  }

  // ========================================
  // TTS Audio Player
  // ========================================
  function initAudioPlayer() {
    audioPlayer = new Audio();
    audioPlayer.addEventListener('ended', onAudioEnded);
    audioPlayer.addEventListener('error', onAudioError);
  }

  function playSharkAudio(audioData, sharkId, duration) {
    if (!audioData || !audioData.audioData) {
      // No audio data, just use estimated duration for speaking indicator
      if (duration > 0) {
        setTimeout(() => {
          setSpeakingIndicator(sharkId, false);
        }, duration);
      }
      return;
    }

    // Queue the audio
    audioQueue.push({
      data: audioData.audioData,
      format: audioData.format || 'audio/mpeg',
      sharkId: sharkId
    });

    // Start playing if not already
    if (!isPlayingAudio) {
      playNextAudio();
    }
  }

  function playNextAudio() {
    if (audioQueue.length === 0) {
      isPlayingAudio = false;
      return;
    }

    isPlayingAudio = true;
    const item = audioQueue.shift();

    // Convert base64 to blob URL
    const byteChars = atob(item.data);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
      byteNumbers[i] = byteChars.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: item.format });
    const audioUrl = URL.createObjectURL(blob);

    // Store current shark for when audio ends
    audioPlayer.dataset.currentShark = item.sharkId;

    // Play
    audioPlayer.src = audioUrl;
    audioPlayer.play().catch(err => {
      console.log('Audio playback failed:', err);
      onAudioEnded();
    });
  }

  function onAudioEnded() {
    // Clear speaking indicator for the shark that just finished
    const sharkId = audioPlayer.dataset.currentShark;
    if (sharkId) {
      setSpeakingIndicator(sharkId, false);
    }

    // Clean up blob URL
    if (audioPlayer.src.startsWith('blob:')) {
      URL.revokeObjectURL(audioPlayer.src);
    }

    // Play next in queue
    playNextAudio();
  }

  function onAudioError(e) {
    console.log('Audio error:', e);
    onAudioEnded();
  }

  function checkAllSharksOut() {
    // Use more specific selector - only participant divs, not confidence bars
    const allParticipants = document.querySelectorAll('.participant[data-investor]');
    let allOut = true;
    let outCount = 0;

    allParticipants.forEach(p => {
      const video = p.querySelector('.participant-video');
      if (!video) return; // Skip if no video element found

      if (video.classList.contains('participant-video--out')) {
        outCount++;
      } else {
        allOut = false;
      }
    });

    console.log('[checkAllSharksOut] Out count:', outCount, '/', allParticipants.length, 'allOut:', allOut);

    if (allOut && allParticipants.length > 0 && outCount === allParticipants.length) {
      // All sharks are out - show sad ending
      console.log('[checkAllSharksOut] All sharks are out! Showing sad ending.');
      showSadEnding();
    }
  }

  function showSadEnding() {
    // Stop the timer
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Disconnect SSE
    disconnectSSE();

    // Update phase
    currentPhase = 'closed';
    updatePhaseIndicator();

    // Play sad music
    playSadMusic();

    // Show ending message
    sendSystemMessage("All sharks are out. Better luck next time!");

    // Show sad overlay
    const overlay = document.createElement('div');
    overlay.className = 'ending-overlay ending-overlay--sad';
    overlay.innerHTML = `
      <div class="ending-content">
        <div class="ending-icon">😔</div>
        <h2 class="ending-title">No Deal</h2>
        <p class="ending-subtitle">All sharks have passed on your pitch.</p>
        <p class="ending-message">Don't give up! Many successful entrepreneurs faced rejection before finding their breakthrough.</p>
        <button class="ending-btn" onclick="location.reload()">Try Again</button>
      </div>
    `;
    document.body.appendChild(overlay);

    // Fade in
    setTimeout(() => overlay.classList.add('visible'), 100);
  }

  function playSadMusic() {
    // Create sad ambient tone using Web Audio API
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

    // Create a melancholic chord progression
    const playNote = (freq, startTime, duration, gain = 0.1) => {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.value = freq;

      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(gain, startTime + 0.1);
      gainNode.gain.linearRampToValueAtTime(0, startTime + duration);

      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      osc.start(startTime);
      osc.stop(startTime + duration);
    };

    // D minor chord (sad)
    const now = audioCtx.currentTime;
    playNote(146.83, now, 4, 0.08);      // D3
    playNote(174.61, now, 4, 0.08);      // F3
    playNote(220.00, now, 4, 0.08);      // A3

    // Fade to Am
    playNote(130.81, now + 3, 4, 0.06);  // C3
    playNote(164.81, now + 3, 4, 0.06);  // E3
    playNote(220.00, now + 3, 4, 0.06);  // A3
  }

  function setSharkOut(sharkId, message) {
    const participant = document.querySelector(`[data-investor="${sharkId}"]`);
    if (!participant) return;

    // Update state
    participant.dataset.state = 'out';

    // Update visual
    const video = participant.querySelector('.participant-video');
    video.classList.add('participant-video--out');
    participant.classList.add('participant--out');

    // Update badge
    const badge = participant.querySelector('.participant-badge');
    if (badge) {
      badge.classList.remove('badge--live', 'badge--interested');
      badge.classList.add('badge--out');
      badge.textContent = 'OUT';
    }

    // Note: Don't send message here - it's already sent via shark_message event

    // Update local state
    if (sharkStates[sharkId]) {
      sharkStates[sharkId].status = 'out';
    }
  }

  // ========================================
  // Phase Indicator
  // ========================================
  function updatePhaseIndicator() {
    const meetingTitle = document.getElementById('meetingTitle');
    if (!meetingTitle || !pitchData) return;

    switch (currentPhase) {
      case 'pitch':
        meetingTitle.textContent = `${pitchData.companyName} — Pitch Phase`;
        break;
      case 'qa':
        meetingTitle.textContent = `${pitchData.companyName} — Q&A`;
        break;
      case 'offers':
        meetingTitle.textContent = `${pitchData.companyName} — Negotiation`;
        break;
      case 'closed':
        meetingTitle.textContent = `${pitchData.companyName} — Deal Closed!`;
        break;
    }

    // Update timer state based on phase
    const timerDisplay = document.getElementById('timerDisplay');
    const pressureBar = document.getElementById('pressureBar');
    if (currentPhase !== 'pitch') {
      if (timerDisplay) timerDisplay.dataset.state = 'neutral';
      if (pressureBar) pressureBar.dataset.state = 'neutral';
    }
  }

  // ========================================
  // Chat Input & Record Button
  // ========================================
  let chatRecognition = null;
  let isRecording = false;

  function initChatInput() {
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.querySelector('.send-btn');
    const recordBtn = document.getElementById('recordBtn');

    if (!chatInput || !sendBtn) return;

    const sendMessage = async () => {
      const text = chatInput.value.trim();
      if (!text) return;

      // Clear input
      chatInput.value = '';

      // Show user message in chat
      sendUserMessage(text);

      // Update context
      conversationContext += `\nYou: ${text}`;

      // Send to backend
      if (USE_SSE && sessionId) {
        // SSE mode
        try {
          await fetch(`${API_BASE}/api/session/${sessionId}/user-message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
          });
        } catch (err) {
          console.log('Failed to send message to backend');
        }
      } else {
        // Serverless mode
        callServerlessChat(text, false);
      }
    };

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
      }
    });

    // Record button - toggle mode (press to start, press to stop)
    if (recordBtn) {
      recordBtn.addEventListener('click', toggleRecording);
    }
  }

  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  // MediaRecorder for Whisper transcription
  let mediaRecorder = null;
  let audioChunks = [];

  async function startRecording() {
    if (isRecording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      isRecording = true;
      audioChunks = [];

      const recordBtn = document.getElementById('recordBtn');
      const transcriptArea = document.getElementById('chatTranscript');
      const liveText = document.getElementById('liveTranscriptText');

      if (recordBtn) recordBtn.classList.add('recording');
      if (transcriptArea) transcriptArea.style.display = 'block';
      if (liveText) liveText.textContent = 'Recording... Press mic again to stop';

      // Use a format Whisper supports
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : '';
      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());

        if (audioChunks.length === 0) return;

        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });

        // Determine file extension from mime type
        const ext = mediaRecorder.mimeType.includes('mp4') ? 'mp4' : 'webm';

        // Show transcribing status
        if (liveText) liveText.textContent = 'Transcribing...';

        // Send to Whisper API
        const formData = new FormData();
        formData.append('audio', audioBlob, `recording.${ext}`);

        try {
          const response = await fetch(`${API_BASE}/api/transcribe`, {
            method: 'POST',
            body: formData
          });

          const result = await response.json();

          if (result.success && result.text) {
            // Update chat input with transcribed text
            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
              chatInput.value = result.text;
            }
            if (liveText) liveText.textContent = result.text;

            // Auto-hide after showing result
            setTimeout(() => {
              const transcriptArea = document.getElementById('chatTranscript');
              if (transcriptArea) transcriptArea.style.display = 'none';
            }, 2000);
          } else {
            if (liveText) liveText.textContent = result.error || 'Transcription failed';
            setTimeout(() => {
              const transcriptArea = document.getElementById('chatTranscript');
              if (transcriptArea) transcriptArea.style.display = 'none';
            }, 2000);
          }
        } catch (err) {
          console.log('Transcription error:', err);
          if (liveText) liveText.textContent = 'Transcription failed';
          setTimeout(() => {
            const transcriptArea = document.getElementById('chatTranscript');
            if (transcriptArea) transcriptArea.style.display = 'none';
          }, 2000);
        }
      };

      mediaRecorder.start();

    } catch (err) {
      console.log('Could not start recording:', err);
      alert('Microphone access denied. Please allow microphone access.');
    }
  }

  function stopRecording() {
    if (!isRecording) return;

    isRecording = false;
    const recordBtn = document.getElementById('recordBtn');

    if (recordBtn) recordBtn.classList.remove('recording');

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }

  function sendUserMessage(text) {
    // Hide response guidance when user sends a message
    hasUserResponded = true;
    hideResponseGuidance();

    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    const now = new Date();
    const time = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });

    const message = document.createElement('div');
    message.className = 'message message--user';
    message.innerHTML = `
      <div class="message-header">
        <span class="message-author">You</span>
        <span class="message-time">${time}</span>
      </div>
      <p class="message-text">${text}</p>
    `;

    messagesContainer.appendChild(message);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // ========================================
  // Transcript Panel
  // ========================================
  function initTranscriptToggle() {
    const toggleBtn = document.getElementById('transcriptToggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleTranscript);
    }
  }

  function toggleTranscript() {
    const panel = document.getElementById('transcriptPanel');
    const toggleBtn = document.getElementById('transcriptToggle');
    if (!panel) return;

    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'flex';
    if (toggleBtn) {
      toggleBtn.classList.toggle('active', !isVisible);
    }
  }

  function addToTranscriptPanel(entry) {
    const content = document.getElementById('transcriptContent');
    if (!content) return;

    // Remove empty message if present
    const emptyMsg = content.querySelector('.transcript-empty');
    if (emptyMsg) emptyMsg.remove();

    const entryDiv = document.createElement('div');
    entryDiv.className = 'transcript-entry';

    const timeStr = formatTime(entry.timeRemaining);
    entryDiv.innerHTML = `
      <div class="transcript-time">${timeStr} remaining</div>
      <div class="transcript-text">${entry.text}</div>
    `;

    content.appendChild(entryDiv);
    content.scrollTop = content.scrollHeight;
  }

  // ========================================
  // Webcam
  // ========================================
  async function initWebcam() {
    const webcamMain = document.getElementById('userWebcamMain');
    const webcamSmall = document.getElementById('userWebcamSmall');
    const avatarContainer = document.getElementById('featuredAvatarContainer');
    const avatarSmall = document.getElementById('userAvatarSmall');
    const mobilePreview = document.getElementById('mobileUserPreview');
    const mobileWebcam = document.getElementById('mobileUserWebcam');

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });

      if (webcamMain) {
        webcamMain.srcObject = mediaStream;
        if (avatarContainer) avatarContainer.style.display = 'none';
      }

      if (webcamSmall) {
        webcamSmall.srcObject = mediaStream;
        if (avatarSmall) avatarSmall.style.display = 'none';
      }

      // Mobile user preview
      if (mobileWebcam) {
        mobileWebcam.srcObject = mediaStream;
        if (mobilePreview) mobilePreview.classList.add('has-webcam');
      }

    } catch (err) {
      console.log('Webcam not available:', err.message);
      // Keep showing avatar fallback
    }
  }

  function stopWebcam() {
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
  }

  // ========================================
  // Camera Toggle
  // ========================================
  let cameraEnabled = true;

  function toggleCamera() {
    const btn = document.getElementById('cameraToggleBtn');
    const onIcon = btn?.querySelector('.camera-on-icon');
    const offIcon = btn?.querySelector('.camera-off-icon');
    const webcamMain = document.getElementById('userWebcamMain');
    const webcamSmall = document.getElementById('userWebcamSmall');
    const avatarContainer = document.getElementById('featuredAvatarContainer');
    const avatarSmall = document.getElementById('userAvatarSmall');
    const mobilePreview = document.getElementById('mobileUserPreview');
    const mobileWebcam = document.getElementById('mobileUserWebcam');

    if (cameraEnabled) {
      // Turn off camera
      if (mediaStream) {
        mediaStream.getVideoTracks().forEach(track => track.enabled = false);
      }
      if (webcamMain) webcamMain.style.display = 'none';
      if (webcamSmall) webcamSmall.style.display = 'none';
      if (mobileWebcam) mobileWebcam.style.display = 'none';
      if (avatarContainer) avatarContainer.style.display = 'flex';
      if (avatarSmall) avatarSmall.style.display = 'flex';
      if (mobilePreview) mobilePreview.classList.remove('has-webcam');
      if (onIcon) onIcon.style.display = 'none';
      if (offIcon) offIcon.style.display = 'block';
      if (btn) {
        btn.classList.add('camera-off');
        btn.title = 'Turn on camera';
      }
      cameraEnabled = false;
    } else {
      // Turn on camera
      if (mediaStream) {
        mediaStream.getVideoTracks().forEach(track => track.enabled = true);
      }
      if (webcamMain) webcamMain.style.display = 'block';
      if (webcamSmall) webcamSmall.style.display = 'block';
      if (mobileWebcam) mobileWebcam.style.display = 'block';
      if (avatarContainer) avatarContainer.style.display = 'none';
      if (avatarSmall) avatarSmall.style.display = 'none';
      if (mobilePreview) mobilePreview.classList.add('has-webcam');
      if (onIcon) onIcon.style.display = 'block';
      if (offIcon) offIcon.style.display = 'none';
      if (btn) {
        btn.classList.remove('camera-off');
        btn.title = 'Turn off camera';
      }
      cameraEnabled = true;
    }
  }

  // Initialize camera toggle button
  function initCameraToggle() {
    const btn = document.getElementById('cameraToggleBtn');
    if (btn) {
      btn.addEventListener('click', toggleCamera);
    }
  }

  // ========================================
  // Response Guidance
  // ========================================
  let hasShownGuidance = false;
  let hasUserResponded = false;

  function showResponseGuidance() {
    if (hasShownGuidance || hasUserResponded) return;
    const guidance = document.getElementById('responseGuidance');
    if (guidance) {
      guidance.classList.add('visible');
      hasShownGuidance = true;
    }
  }

  function hideResponseGuidance() {
    const guidance = document.getElementById('responseGuidance');
    if (guidance) {
      guidance.classList.remove('visible');
    }
  }

  function initResponseGuidance() {
    const closeBtn = document.getElementById('guidanceCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', hideResponseGuidance);
    }
  }

  // ========================================
  // Speech Recognition (Whisper-based)
  // ========================================
  let pitchRecorder = null;
  let pitchAudioChunks = [];
  let pitchAudioStream = null;
  let transcriptionInterval = null;

  async function initSpeechRecognition() {
    // Check if Whisper is available
    try {
      const statusResponse = await fetch(`${API_BASE}/api/transcribe/status`);
      const status = await statusResponse.json();

      if (!status.available) {
        console.log('Whisper not available:', status.message);
        updateCaption('Add OpenAI API key for live transcription');
        showListeningIndicator(false);
        return;
      }
    } catch (err) {
      console.log('Could not check Whisper status:', err);
    }

    // Start recording for pitch phase
    try {
      pitchAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      pitchAudioChunks = [];

      // Use a format Whisper supports - try webm with opus, fall back to default
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : '';
      pitchRecorder = new MediaRecorder(pitchAudioStream, mimeType ? { mimeType } : undefined);

      pitchRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          pitchAudioChunks.push(event.data);
        }
      };

      // Start recording
      pitchRecorder.start(1000); // Collect data every second

      isListening = true;
      showListeningIndicator(true);
      updateCaption('Recording your pitch...');

      // Transcribe every 15 seconds during pitch
      transcriptionInterval = setInterval(async () => {
        if (currentPhase === 'pitch' && pitchAudioChunks.length > 0) {
          await transcribePitchAudio(false);
        }
      }, 15000);

    } catch (err) {
      console.log('Could not start pitch recording:', err);
      updateCaption('Microphone access needed for transcription');
      showListeningIndicator(false);
    }
  }

  async function transcribePitchAudio(isFinal = false) {
    if (pitchAudioChunks.length === 0) return;

    // Get current chunks and clear
    const chunksToTranscribe = [...pitchAudioChunks];
    if (!isFinal) {
      // Keep last chunk for continuity
      pitchAudioChunks = pitchAudioChunks.slice(-1);
    } else {
      pitchAudioChunks = [];
    }

    const mimeType = pitchRecorder ? pitchRecorder.mimeType : 'audio/webm';
    const audioBlob = new Blob(chunksToTranscribe, { type: mimeType });

    // Determine file extension from mime type
    const ext = mimeType.includes('mp4') ? 'mp4' : 'webm';

    // Don't transcribe very short audio
    if (audioBlob.size < 1000) return;

    try {
      updateCaption('Transcribing...');

      const formData = new FormData();
      formData.append('audio', audioBlob, `pitch.${ext}`);

      const response = await fetch(`${API_BASE}/api/transcribe`, {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.success && result.text && result.text.trim()) {
        const entry = {
          text: result.text.trim(),
          timestamp: Date.now(),
          timeRemaining: currentPhase === 'pitch' ? pitchTimeRemaining : remainingSeconds
        };

        // Store transcript
        transcript.push(entry);
        addToTranscriptPanel(entry);

        // Update caption
        updateCaption(result.text.length > 60 ? result.text.slice(-60) + '...' : result.text);
      } else if (!isFinal) {
        updateCaption('Recording your pitch...');
      }
    } catch (err) {
      console.log('Pitch transcription error:', err);
      if (!isFinal) {
        updateCaption('Recording your pitch...');
      }
    }
  }

  async function stopSpeechRecognition() {
    // Clear transcription interval
    if (transcriptionInterval) {
      clearInterval(transcriptionInterval);
      transcriptionInterval = null;
    }

    // Stop pitch recorder and transcribe remaining audio
    if (pitchRecorder && pitchRecorder.state !== 'inactive') {
      pitchRecorder.stop();

      // Transcribe any remaining audio
      if (pitchAudioChunks.length > 0) {
        await transcribePitchAudio(true);
      }
    }

    // Stop audio stream
    if (pitchAudioStream) {
      pitchAudioStream.getTracks().forEach(track => track.stop());
      pitchAudioStream = null;
    }

    pitchRecorder = null;
    pitchAudioChunks = [];

    // Also stop old recognition if exists
    if (recognition) {
      try {
        recognition.stop();
      } catch (e) {}
      recognition = null;
    }

    isListening = false;
    showListeningIndicator(false);
  }

  function updateCaption(text) {
    const captionText = document.getElementById('captionText');
    if (captionText) {
      captionText.textContent = `"${text}"`;
    }
  }

  function showListeningIndicator(show) {
    const indicator = document.getElementById('captionListening');
    if (indicator) {
      indicator.classList.toggle('hidden', !show);
    }
  }

  function hideCaptionArea() {
    const caption = document.getElementById('featuredCaption');
    if (caption) {
      caption.style.display = 'none';
    }
  }

  function showCaptionArea() {
    const caption = document.getElementById('featuredCaption');
    if (caption) {
      caption.style.display = 'flex';
    }
  }

  // ========================================
  // End Pitch / Phase Management
  // ========================================
  function initEndPitch() {
    // Original end button in controls bar
    const endBtn = document.getElementById('endPitchBtn');
    if (endBtn) {
      endBtn.addEventListener('click', endPitchPhase);
    }

    // End button in chat tabs (next to Offers)
    const endPitchTabBtn = document.getElementById('endPitchTabBtn');
    if (endPitchTabBtn) {
      endPitchTabBtn.addEventListener('click', endPitchPhase);
    }
  }

  async function endPitchPhase() {
    console.log('[endPitchPhase] Called with currentPhase:', currentPhase);

    if (currentPhase === 'pitch') {
      // Transition from pitch to Q&A
      console.log('[endPitchPhase] Transitioning from pitch to Q&A');
      currentPhase = 'qa';

      // Store pitch transcript and time used
      window.pitchTranscript = [...transcript];
      window.pitchTimeUsed = PITCH_DURATION - pitchTimeRemaining;

      // Update UI for Q&A phase
      const endBtn = document.getElementById('endPitchBtn');
      if (endBtn) {
        endBtn.textContent = 'Leave Panel';
        endBtn.classList.add('leave-btn--final');
      }

      // Update end button in chat tabs
      const endPitchTabBtn = document.getElementById('endPitchTabBtn');
      if (endPitchTabBtn) {
        endPitchTabBtn.textContent = 'Leave Panel';
        endPitchTabBtn.classList.add('leave-mode');
      }

      // Update caption
      updateCaption('Q&A with the investors has begun...');

      // Send system message
      sendSystemMessage('Your pitch has ended. The investors will now respond.');

      // Reset timer state to neutral for Q&A (less pressure)
      const timerDisplay = document.getElementById('timerDisplay');
      if (timerDisplay) {
        timerDisplay.dataset.state = 'neutral';
      }

      const pressureBar = document.getElementById('pressureBar');
      if (pressureBar) {
        pressureBar.dataset.state = 'neutral';
      }

      // Update phase indicator
      updatePhaseIndicator();

      console.log('Pitch phase ended. Entering Q&A phase.');
      console.log('Pitch transcript:', window.pitchTranscript);

      // Submit pitch to backend
      if (USE_SSE && sessionId) {
        // SSE mode: use Flask backend
        try {
          const response = await fetch(`${API_BASE}/api/session/${sessionId}/pitch-complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transcript: transcript,
              pitchDuration: window.pitchTimeUsed
            })
          });

          if (response.ok) {
            const data = await response.json();
            console.log('Pitch submitted, confidence scores:', data.confidenceScores);
          }
        } catch (err) {
          console.log('Failed to submit pitch to backend');
        }
      } else {
        // Serverless mode: call chat API directly
        callServerlessChat(null, true);
      }

    } else if (currentPhase === 'closed') {
      // Deal is done, show summary
      console.log('[endPitchPhase] Phase is closed, showing deal summary');
      showDealSummary();
    } else {
      // Q&A phase - clicking "Leave Panel" ends the session
      console.log('[endPitchPhase] Phase is', currentPhase, '- ending session');
      endSession();
    }
  }

  // ========================================
  // Offers Panel Tab Management
  // ========================================
  const OFFER_DURATION = 300; // 5 minutes to consider an offer
  let offerTimers = {}; // Track countdown timers by offer ID

  function initOffersTabs() {
    const chatTabBtn = document.getElementById('chatTabBtn');
    const offersTabBtn = document.getElementById('offersTabBtn');

    if (chatTabBtn) {
      chatTabBtn.addEventListener('click', () => switchTab('chat'));
    }
    if (offersTabBtn) {
      offersTabBtn.addEventListener('click', () => switchTab('offers'));
    }
  }

  function switchTab(tab) {
    const chatMessages = document.getElementById('chatMessages');
    const offersPanel = document.getElementById('offersPanel');
    const chatTabBtn = document.getElementById('chatTabBtn');
    const offersTabBtn = document.getElementById('offersTabBtn');

    if (tab === 'chat') {
      chatMessages.style.display = 'flex';
      offersPanel.style.display = 'none';
      chatTabBtn.classList.add('chat-tab--active');
      offersTabBtn.classList.remove('chat-tab--active');
    } else {
      chatMessages.style.display = 'none';
      offersPanel.style.display = 'flex';
      chatTabBtn.classList.remove('chat-tab--active');
      offersTabBtn.classList.add('chat-tab--active');
    }
  }

  function updateOffersBadge() {
    const badge = document.getElementById('offersBadge');
    const activeOffers = pendingOffers.filter(o => o.status !== 'expired' && o.status !== 'accepted' && o.status !== 'declined');
    if (badge) {
      if (activeOffers.length > 0) {
        badge.textContent = activeOffers.length;
        badge.style.display = 'inline-flex';
      } else {
        badge.style.display = 'none';
      }
    }

    // Update empty state
    const offersEmpty = document.getElementById('offersEmpty');
    const offersList = document.getElementById('offersList');
    if (offersEmpty && offersList) {
      offersEmpty.style.display = activeOffers.length === 0 ? 'block' : 'none';
    }
  }

  // ========================================
  // Offer Handling
  // ========================================
  // Deal type display names
  const DEAL_TYPE_LABELS = {
    'cash_equity': 'Cash for Equity',
    'safe_cap': 'SAFE Note',
    'safe_milestone': 'SAFE + Milestone',
    'tranche': 'Tranche Investment',
    'royalty': 'Royalty Deal',
    'no_offer': 'Conditional'
  };

  function addOfferToUI(offer) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    // Add timestamp for expiration tracking
    offer.createdAt = Date.now();
    offer.status = 'active';
    pendingOffers.push(offer);

    // Add to offers panel with timer
    addOfferToPanelUI(offer);
    updateOffersBadge();

    const offerCard = document.createElement('div');
    offerCard.className = 'offer-card';
    offerCard.dataset.offerId = offer.id;

    // Determine deal type display
    const dealType = offer.deal_type || 'cash_equity';
    const dealLabel = DEAL_TYPE_LABELS[dealType] || 'Offer';

    // Build terms HTML based on deal type
    let termsHtml = '';

    if (dealType === 'cash_equity' || !offer.terms) {
      // Standard cash for equity
      termsHtml = `<span class="offer-amount">$${(offer.amount || 0).toLocaleString()}</span>
                   <span class="offer-for">for</span>
                   <span class="offer-equity">${offer.equity || 0}%</span>`;
    } else if (dealType === 'safe_cap' && offer.terms) {
      // SAFE with valuation cap
      termsHtml = `<span class="offer-amount">$${(offer.terms.amount || offer.amount || 0).toLocaleString()}</span>
                   <span class="offer-for">SAFE with</span>
                   <span class="offer-equity">$${(offer.terms.valuation_cap || 0).toLocaleString()} cap</span>`;
    } else if (dealType === 'safe_milestone' && offer.terms) {
      // SAFE with milestone
      termsHtml = `<span class="offer-amount">$${(offer.terms.amount || offer.amount || 0).toLocaleString()}</span>
                   <span class="offer-for">converts at</span>
                   <span class="offer-equity">$${(offer.terms.valuation_cap || 0).toLocaleString()} cap</span>`;
    } else if (dealType === 'tranche' && offer.terms?.tranches) {
      // Tranche investment
      const firstTranche = offer.terms.tranches[0];
      termsHtml = `<span class="offer-amount">$${(firstTranche?.amount || 0).toLocaleString()} now</span>
                   <span class="offer-for">of</span>
                   <span class="offer-equity">$${(offer.terms.total_amount || offer.amount || 0).toLocaleString()} total</span>`;
    } else if (dealType === 'royalty') {
      // Royalty deal
      termsHtml = `<span class="offer-amount">$${(offer.amount || 0).toLocaleString()}</span>
                   <span class="offer-for">for</span>
                   <span class="offer-equity">${offer.equity || 0}%</span>`;
    } else {
      // Fallback
      termsHtml = `<span class="offer-amount">$${(offer.amount || 0).toLocaleString()}</span>
                   <span class="offer-for">for</span>
                   <span class="offer-equity">${offer.equity || 0}%</span>`;
    }

    // Add royalty info if present
    if (offer.royalty || (offer.terms?.royalty_percent)) {
      const royaltyPct = offer.royalty || offer.terms?.royalty_percent;
      const royaltyCap = offer.royaltyUntil || offer.terms?.royalty_cap || offer.amount;
      termsHtml += `<span class="offer-royalty">+ $${royaltyPct}/unit until $${royaltyCap?.toLocaleString()} recouped</span>`;
    }

    // Add conditions if present
    if (offer.conditions && offer.conditions.length > 0) {
      termsHtml += `<div class="offer-conditions"><strong>Conditions:</strong> ${offer.conditions.join(', ')}</div>`;
    }

    // Add rationale if present
    if (offer.rationale) {
      termsHtml += `<div class="offer-rationale"><em>${offer.rationale}</em></div>`;
    }

    // Add implied valuation if present
    if (offer.implied_valuation && offer.implied_valuation > 0) {
      termsHtml += `<div class="offer-valuation">Implied valuation: $${offer.implied_valuation.toLocaleString()}</div>`;
    }

    offerCard.innerHTML = `
      <div class="offer-header">
        <span class="offer-shark">${offer.sharkName}</span>
        <span class="offer-badge offer-badge--${dealType}">${dealLabel}</span>
      </div>
      <div class="offer-terms">
        ${termsHtml}
      </div>
      <div class="offer-actions">
        <button class="offer-btn offer-btn--accept" onclick="window.acceptOffer('${offer.id}')">Accept</button>
        <button class="offer-btn offer-btn--counter" onclick="window.showCounterModal('${offer.id}')">Counter</button>
        <button class="offer-btn offer-btn--decline" onclick="window.declineOffer('${offer.id}')">Decline</button>
        <button class="offer-btn offer-btn--reply" onclick="window.replyToShark('${offer.sharkName}')">Reply</button>
      </div>
    `;

    messagesContainer.appendChild(offerCard);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function addOfferToPanelUI(offer) {
    const offersList = document.getElementById('offersList');
    if (!offersList) return;

    const card = document.createElement('div');
    card.className = 'offer-panel-card';
    card.id = `panel-offer-${offer.id}`;

    // Determine deal type
    const dealType = offer.deal_type || 'cash_equity';
    const dealLabel = DEAL_TYPE_LABELS[dealType] || 'Offer';

    // Build terms text based on deal type
    let termsText = '';
    if (dealType === 'safe_cap' && offer.terms?.valuation_cap) {
      termsText = `$${(offer.terms.amount || offer.amount || 0).toLocaleString()} SAFE @ $${offer.terms.valuation_cap.toLocaleString()} cap`;
    } else if (dealType === 'safe_milestone' && offer.terms?.valuation_cap) {
      termsText = `$${(offer.terms.amount || offer.amount || 0).toLocaleString()} SAFE + milestone`;
    } else if (dealType === 'tranche' && offer.terms?.total_amount) {
      termsText = `$${offer.terms.total_amount.toLocaleString()} in tranches`;
    } else {
      termsText = `$${(offer.amount || 0).toLocaleString()} for ${offer.equity || 0}%`;
    }

    if (offer.royalty || offer.terms?.royalty_percent) {
      const royaltyPct = offer.royalty || offer.terms?.royalty_percent;
      termsText += ` + $${royaltyPct}/unit royalty`;
    }

    card.innerHTML = `
      <div class="offer-panel-header">
        <span class="offer-panel-shark">${offer.sharkName}</span>
        <span class="offer-panel-type">${dealLabel}</span>
        <span class="offer-panel-timer" id="timer-${offer.id}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span class="timer-seconds">${Math.floor(OFFER_DURATION / 60)}:00</span>
        </span>
      </div>
      <div class="offer-panel-terms">
        <span class="amount">${termsText}</span>
        ${offer.conditions?.length ? `<div class="conditions"><small>${offer.conditions.join(', ')}</small></div>` : ''}
        ${offer.rationale ? `<div class="rationale"><em>${offer.rationale}</em></div>` : ''}
      </div>
      <div class="offer-panel-actions">
        <button class="offer-btn offer-btn--accept" onclick="window.acceptOffer('${offer.id}')">Accept</button>
        <button class="offer-btn offer-btn--counter" onclick="window.showCounterModal('${offer.id}')">Counter</button>
        <button class="offer-btn offer-btn--decline" onclick="window.declineOffer('${offer.id}')">Decline</button>
      </div>
    `;

    offersList.appendChild(card);

    // Start countdown timer
    startOfferTimer(offer.id);
  }

  function startOfferTimer(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    // Clear any existing timer
    if (offerTimers[offerId]) {
      clearInterval(offerTimers[offerId]);
    }

    offerTimers[offerId] = setInterval(() => {
      const elapsed = Math.floor((Date.now() - offer.createdAt) / 1000);
      const remaining = OFFER_DURATION - elapsed;

      const timerEl = document.getElementById(`timer-${offerId}`);
      if (timerEl) {
        const secondsSpan = timerEl.querySelector('.timer-seconds');
        if (secondsSpan) {
          const mins = Math.floor(Math.max(0, remaining) / 60);
          const secs = Math.max(0, remaining) % 60;
          secondsSpan.textContent = mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `${secs}s`;
        }

        // Update timer styling based on remaining time
        timerEl.classList.remove('expiring', 'critical');
        if (remaining <= 60 && remaining > 15) {
          timerEl.classList.add('expiring');
        } else if (remaining <= 15) {
          timerEl.classList.add('critical');
        }
      }

      // Handle expiration
      if (remaining <= 0) {
        handleOfferExpired(offerId);
      }
    }, 1000);
  }

  function handleOfferExpired(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer || offer.status !== 'active') return;

    // Stop timer
    if (offerTimers[offerId]) {
      clearInterval(offerTimers[offerId]);
      delete offerTimers[offerId];
    }

    offer.status = 'expired';

    // Remove from panel
    const panelCard = document.getElementById(`panel-offer-${offerId}`);
    if (panelCard) {
      panelCard.remove();
    }

    // Disable buttons in chat
    const chatCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (chatCard) {
      chatCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
      chatCard.classList.add('offer-card--expired');
    }

    updateOffersBadge();

    // Notify user
    sendSystemMessage(`${offer.sharkName}'s offer has expired.`);

    // Notify backend about expiration (backend will decide if shark goes out)
    if (sessionId) {
      fetch(`${API_BASE}/api/session/${sessionId}/offer-expired`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offerId, sharkId: offer.sharkId })
      }).catch(err => console.log('Failed to notify backend of offer expiration'));
    }
  }

  function removeOfferFromPanel(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (offer) {
      offer.status = 'handled';
    }

    // Stop timer
    if (offerTimers[offerId]) {
      clearInterval(offerTimers[offerId]);
      delete offerTimers[offerId];
    }

    // Remove from panel
    const panelCard = document.getElementById(`panel-offer-${offerId}`);
    if (panelCard) {
      panelCard.remove();
    }

    updateOffersBadge();
  }

  async function acceptOffer(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    offer.status = 'accepted';

    // Remove from offers panel
    removeOfferFromPanel(offerId);

    // Disable offer buttons in chat
    const offerCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (offerCard) {
      offerCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
    }

    sendSystemMessage(`You accepted ${offer.sharkName}'s offer!`);

    if (sessionId) {
      try {
        const response = await fetch(`${API_BASE}/api/session/${sessionId}/offer-response`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ offerId, action: 'accept' })
        });
        const data = await response.json();

        // Check for errors from backend
        if (!response.ok || data.error) {
          console.error('Acceptance failed:', data.error || response.statusText);
          sendSystemMessage(`Error: ${data.error || 'Failed to process acceptance'}. Closing deal manually.`);
          // Force close the deal with the offer we have locally
          setTimeout(() => {
            if (currentPhase !== 'closed') {
              showDealClosed({
                sharkId: offer.sharkId,
                sharkName: offer.sharkName,
                offer: offer
              });
            }
          }, 500);
          return;
        }

        // Fallback: if SSE doesn't deliver deal_closed, handle it here
        if (data.result === 'deal_closed' && data.offer) {
          // Give SSE a moment to deliver, then force close if still not closed
          setTimeout(() => {
            if (currentPhase !== 'closed') {
              console.log('SSE did not deliver deal_closed, using API response fallback');
              showDealClosed({
                sharkId: offer.sharkId,
                sharkName: offer.sharkName,
                offer: data.offer
              });
            }
          }, 1000);
        }
      } catch (err) {
        console.log('Failed to send acceptance to backend:', err);
        // Force close the deal with the offer we have locally
        sendSystemMessage(`Network error, closing deal manually.`);
        setTimeout(() => {
          if (currentPhase !== 'closed') {
            showDealClosed({
              sharkId: offer.sharkId,
              sharkName: offer.sharkName,
              offer: offer
            });
          }
        }, 500);
      }
    }
  }

  async function declineOffer(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    offer.status = 'declined';

    // Remove from offers panel
    removeOfferFromPanel(offerId);

    // Disable offer buttons in chat
    const offerCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (offerCard) {
      offerCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
      offerCard.classList.add('offer-card--declined');
    }

    sendSystemMessage(`You declined ${offer.sharkName}'s offer.`);

    if (sessionId) {
      try {
        await fetch(`${API_BASE}/api/session/${sessionId}/offer-response`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ offerId, action: 'decline' })
        });
      } catch (err) {
        console.log('Failed to send decline to backend');
      }
    }
  }

  function showCounterModal(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    const modal = document.getElementById('counterOfferModal');
    if (!modal) return;

    // Display original offer terms
    const originalTermsEl = document.getElementById('originalOfferTerms');
    if (originalTermsEl) {
      let termsText = `$${(offer.amount || 0).toLocaleString()} for ${offer.equity || 0}%`;
      if (offer.royalty) {
        termsText += ` + $${offer.royalty}/unit royalty`;
      }
      if (offer.deal_type && offer.deal_type !== 'cash_equity') {
        const dealLabels = {
          'royalty': 'Royalty Deal',
          'safe_cap': 'SAFE Note',
          'safe_milestone': 'SAFE + Milestone',
          'tranche': 'Tranche Investment'
        };
        termsText += ` (${dealLabels[offer.deal_type] || offer.deal_type})`;
      }
      originalTermsEl.textContent = termsText;
    }

    // Set form values - start with their offer as base
    document.getElementById('counterAmount').value = offer.amount || 100000;
    document.getElementById('counterEquity').value = Math.max((offer.equity || 10) - 5, 0);
    document.getElementById('counterOfferId').value = offerId;
    document.getElementById('counterSharkName').textContent = offer.sharkName;

    // Handle royalty deals
    const dealType = offer.deal_type || 'cash_equity';
    document.getElementById('counterDealType').value = dealType;

    const royaltyFields = document.getElementById('royaltyFields');
    if (royaltyFields) {
      if (dealType === 'royalty' || offer.royalty) {
        royaltyFields.style.display = 'block';
        // Start with lower royalty as counter
        document.getElementById('counterRoyalty').value = Math.max((offer.royalty || 2) - 0.5, 0.5);
      } else {
        royaltyFields.style.display = 'none';
      }
    }

    modal.style.display = 'flex';
  }

  function hideCounterModal() {
    const modal = document.getElementById('counterOfferModal');
    if (modal) {
      modal.style.display = 'none';
    }
  }

  async function submitCounterOffer() {
    const offerId = document.getElementById('counterOfferId').value;
    const amount = parseInt(document.getElementById('counterAmount').value);
    const equity = parseInt(document.getElementById('counterEquity').value);
    const dealType = document.getElementById('counterDealType').value;

    // Get royalty if it's a royalty deal
    let royalty = null;
    const royaltyInput = document.getElementById('counterRoyalty');
    if (royaltyInput && document.getElementById('royaltyFields').style.display !== 'none') {
      royalty = parseFloat(royaltyInput.value);
    }

    hideCounterModal();

    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    // Disable offer buttons
    const offerCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (offerCard) {
      offerCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
    }

    // Build counter message
    let counterMsg = `Counter offer to ${offer.sharkName}: $${amount.toLocaleString()} for ${equity}%`;
    if (royalty !== null) {
      counterMsg += ` with $${royalty}/unit royalty`;
    }
    sendUserMessage(counterMsg);

    if (sessionId) {
      try {
        const counterTerms = { amount, equity };
        if (royalty !== null) {
          counterTerms.royalty = royalty;
        }

        await fetch(`${API_BASE}/api/session/${sessionId}/offer-response`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            offerId,
            action: 'counter',
            counterTerms
          })
        });
      } catch (err) {
        console.log('Failed to send counter to backend');
      }
    }
  }

  function replyToShark(sharkName) {
    // Focus the chat input and prefill with shark name for direct reply
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.value = `@${sharkName}: `;
      chatInput.focus();
      // Move cursor to end
      chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
    }
  }

  function showDealClosed(data) {
    // Prevent duplicate overlays
    if (document.querySelector('.ending-overlay--success')) {
      console.log('Deal overlay already shown, skipping duplicate');
      return;
    }

    // Stop the timer
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Disconnect SSE
    disconnectSSE();

    // Update phase
    currentPhase = 'closed';
    updatePhaseIndicator();

    const offer = data.offer;

    // Play success music
    playSuccessMusic();

    // Build royalty text if present
    let royaltyText = '';
    if (offer.royalty) {
      royaltyText = `<div class="deal-royalty">+ $${offer.royalty}/unit royalty</div>`;
    }

    // Show success overlay
    const overlay = document.createElement('div');
    overlay.className = 'ending-overlay ending-overlay--success';
    overlay.id = 'dealClosedOverlay';
    overlay.innerHTML = `
      <div class="ending-content">
        <div class="ending-icon">🎉</div>
        <h2 class="ending-title">DEAL!</h2>
        <p class="ending-subtitle">Congratulations! You got a deal!</p>
        <div class="deal-details">
          <div class="deal-shark">${data.sharkName}</div>
          <div class="deal-terms">
            <span class="deal-amount">$${(offer.amount || 0).toLocaleString()}</span>
            <span class="deal-for">for</span>
            <span class="deal-equity">${offer.equity || 0}%</span>
          </div>
          ${royaltyText}
        </div>
        <button class="ending-btn ending-btn--share" onclick="window.showDealCard(window.lastDealData)">Share Your Deal</button>
        <button class="ending-btn ending-btn--secondary" onclick="location.reload()">New Pitch</button>
      </div>
    `;
    document.body.appendChild(overlay);

    // Ensure overlay stays on top
    overlay.style.zIndex = '9999';

    // Store deal data for sharing
    window.lastDealData = data;

    // Auto-show deal card after 2 seconds
    setTimeout(() => {
      showDealCard(data);
    }, 2500);
  }

  // ========================================
  // New Deal Flow UI Functions
  // ========================================

  function showBiddingWarIndicator(data) {
    // Show notification that bidding war has started
    const notification = document.createElement('div');
    notification.className = 'bidding-war-notification';
    notification.innerHTML = `
      <div class="bidding-war-content">
        <span class="bidding-war-icon">⚔️</span>
        <span class="bidding-war-text">BIDDING WAR! ${data.activeOffers?.length || 2} sharks competing!</span>
      </div>
    `;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: linear-gradient(135deg, #ff6b6b, #ffa500);
      color: white;
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: bold;
      z-index: 1000;
      animation: slideDown 0.3s ease, pulse 1s infinite;
      box-shadow: 0 4px 15px rgba(255, 107, 107, 0.4);
    `;
    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
      notification.style.animation = 'slideUp 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 5000);

    // Also update offers tab to highlight competing offers
    const offersTab = document.querySelector('[data-tab="offers"]');
    if (offersTab) {
      offersTab.style.animation = 'pulse 0.5s ease 3';
    }
  }

  function showFinalOfferCountdown(data) {
    // Show countdown timer for final offer
    const countdownOverlay = document.createElement('div');
    countdownOverlay.className = 'final-offer-countdown';
    countdownOverlay.id = 'finalOfferCountdown';

    let secondsLeft = data.countdownSeconds || 30;

    countdownOverlay.innerHTML = `
      <div class="countdown-content">
        <div class="countdown-header">⏰ FINAL OFFER from ${data.sharkName}</div>
        <div class="countdown-timer">${secondsLeft}</div>
        <div class="countdown-message">Accept now or the offer expires!</div>
      </div>
    `;
    countdownOverlay.style.cssText = `
      position: fixed;
      top: 80px;
      right: 20px;
      background: linear-gradient(135deg, #2c3e50, #3498db);
      color: white;
      padding: 16px 24px;
      border-radius: 12px;
      z-index: 999;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      text-align: center;
    `;

    document.body.appendChild(countdownOverlay);

    // Update countdown every second
    const countdownInterval = setInterval(() => {
      secondsLeft--;
      const timerEl = countdownOverlay.querySelector('.countdown-timer');
      if (timerEl) {
        timerEl.textContent = secondsLeft;
        if (secondsLeft <= 10) {
          timerEl.style.color = '#ff6b6b';
          timerEl.style.animation = 'pulse 0.5s ease infinite';
        }
      }

      if (secondsLeft <= 0) {
        clearInterval(countdownInterval);
        countdownOverlay.remove();
      }
    }, 1000);

    // Store interval ID for cleanup
    countdownOverlay.dataset.intervalId = countdownInterval;
  }

  function showProofSatisfied(data) {
    // Show notification when founder satisfies a proof requirement
    let proofs = data.proofs;

    // Handle various data formats
    let proofStrings = [];
    if (Array.isArray(proofs)) {
      proofStrings = proofs.map(p => {
        if (Array.isArray(p)) return p[0];
        if (typeof p === 'object' && p !== null) return p.type || p.name || JSON.stringify(p);
        return String(p);
      });
    } else if (typeof proofs === 'object' && proofs !== null) {
      // It might be an object like {type: 'revenue', value: 50000}
      proofStrings = Object.keys(proofs).length > 0 ? [proofs.type || Object.keys(proofs)[0]] : [];
    } else if (proofs) {
      proofStrings = [String(proofs)];
    }

    if (proofStrings.length === 0) return;

    const notification = document.createElement('div');
    notification.className = 'proof-satisfied-notification';
    notification.innerHTML = `
      <div class="proof-content">
        <span class="proof-icon">✓</span>
        <span class="proof-text">${data.sharkName} acknowledges your ${proofStrings.join(', ')}</span>
      </div>
    `;
    notification.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: linear-gradient(135deg, #2ecc71, #27ae60);
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      z-index: 1000;
      animation: slideIn 0.3s ease;
      box-shadow: 0 4px 15px rgba(46, 204, 113, 0.4);
    `;
    document.body.appendChild(notification);

    // Remove after 4 seconds
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  }

  function showDealRecap(data) {
    // Show a recap of the deal and competing offers
    const recap = data.recap || {};
    const competingOffers = data.competingOffers || [];

    if (competingOffers.length === 0) return;

    // Add deal comparison to the success overlay if it exists
    const overlay = document.querySelector('.ending-overlay--success');
    if (overlay) {
      const comparisonDiv = document.createElement('div');
      comparisonDiv.className = 'deal-comparison';
      comparisonDiv.innerHTML = `
        <h3 style="margin-top: 20px; font-size: 14px; color: #666;">Other offers you passed on:</h3>
        <div class="other-offers" style="display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; justify-content: center;">
          ${competingOffers.map(offer => `
            <div class="passed-offer" style="background: #f0f0f0; padding: 8px 12px; border-radius: 6px; font-size: 12px;">
              <strong>${offer.sharkName}</strong>: $${(offer.amount || 0).toLocaleString()} for ${offer.equity}%
            </div>
          `).join('')}
        </div>
      `;

      const endingContent = overlay.querySelector('.ending-content');
      if (endingContent) {
        endingContent.insertBefore(comparisonDiv, endingContent.querySelector('.ending-btn'));
      }
    }
  }

  function showSessionComplete(data) {
    // Update UI to show session is fully complete
    console.log('Session complete:', data);

    // Stop any remaining countdown
    const countdown = document.getElementById('finalOfferCountdown');
    if (countdown) {
      const intervalId = countdown.dataset.intervalId;
      if (intervalId) clearInterval(parseInt(intervalId));
      countdown.remove();
    }
  }

  function playSuccessMusic() {
    // Create triumphant chord progression using Web Audio API
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

    const playNote = (freq, startTime, duration, gain = 0.1) => {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.value = freq;

      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(gain, startTime + 0.05);
      gainNode.gain.linearRampToValueAtTime(gain * 0.7, startTime + duration * 0.5);
      gainNode.gain.linearRampToValueAtTime(0, startTime + duration);

      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      osc.start(startTime);
      osc.stop(startTime + duration);
    };

    const now = audioCtx.currentTime;

    // C major chord (triumphant)
    playNote(261.63, now, 0.4, 0.12);       // C4
    playNote(329.63, now, 0.4, 0.12);       // E4
    playNote(392.00, now, 0.4, 0.12);       // G4

    // G major
    playNote(196.00, now + 0.4, 0.4, 0.12); // G3
    playNote(246.94, now + 0.4, 0.4, 0.12); // B3
    playNote(293.66, now + 0.4, 0.4, 0.12); // D4

    // C major (higher, finale)
    playNote(523.25, now + 0.8, 1.5, 0.15); // C5
    playNote(659.25, now + 0.8, 1.5, 0.12); // E5
    playNote(783.99, now + 0.8, 1.5, 0.10); // G5
    playNote(1046.50, now + 1.0, 1.3, 0.08); // C6 (sparkle)
  }

  // ========================================
  // Shareable Deal Card
  // ========================================

  let currentDealData = null;

  function showDealCard(dealData) {
    currentDealData = dealData;

    const modal = document.getElementById('dealCardModal');
    if (!modal) return;

    // Populate card data
    const companyName = pitchData?.companyName || 'Your Company';
    const amount = dealData.offer?.amount || 0;
    const equity = dealData.offer?.equity || 0;
    const sharkName = dealData.sharkName || 'Investor';
    const sharkId = dealData.sharkId || 'marcus';
    const valuation = equity > 0 ? Math.round(amount / (equity / 100)) : 0;

    // Update card elements
    const companyEl = document.getElementById('dealCardCompany');
    const amountEl = document.getElementById('dealCardAmount');
    const equityEl = document.getElementById('dealCardEquity');
    const sharkNameEl = document.getElementById('dealCardSharkName');
    const sharkImgEl = document.getElementById('dealCardSharkImg');
    const valuationEl = document.getElementById('dealCardValuation');
    const dateEl = document.getElementById('dealCardDate');

    if (companyEl) companyEl.textContent = companyName;
    if (amountEl) amountEl.textContent = `$${amount.toLocaleString()}`;
    if (equityEl) equityEl.textContent = `${equity}%`;
    if (sharkNameEl) sharkNameEl.textContent = sharkName;
    if (valuationEl) valuationEl.textContent = `Valuation: $${valuation.toLocaleString()}`;
    if (dateEl) dateEl.textContent = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    // Set shark image
    if (sharkImgEl) {
      const sharkImages = {
        marcus: 'images/sharks/marc_cuban.jpg',
        victor: 'images/sharks/kevin_oleary.jpg',
        elena: 'images/sharks/lori_greiner.jpg',
        richard: 'images/sharks/richard_branson.jpg',
        daniel: 'images/sharks/robert_herjavec.jpg'
      };
      sharkImgEl.src = sharkImages[sharkId] || sharkImages.marcus;
    }

    // Show modal
    modal.style.display = 'flex';
  }

  function closeDealCard() {
    const modal = document.getElementById('dealCardModal');
    if (modal) {
      modal.style.display = 'none';
    }
  }

  async function downloadDealCard() {
    const card = document.getElementById('dealCard');
    if (!card) return;

    try {
      // Use html2canvas if available, otherwise create a simple canvas
      if (typeof html2canvas !== 'undefined') {
        const canvas = await html2canvas(card, {
          backgroundColor: '#0f172a',
          scale: 2
        });

        const link = document.createElement('a');
        link.download = `shark-tank-deal-${Date.now()}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
      } else {
        // Fallback: create a simple image using canvas
        const canvas = document.createElement('canvas');
        canvas.width = 800;
        canvas.height = 600;
        const ctx = canvas.getContext('2d');

        // Draw background
        const gradient = ctx.createLinearGradient(0, 0, 800, 600);
        gradient.addColorStop(0, '#0f172a');
        gradient.addColorStop(0.5, '#1e3a5a');
        gradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 800, 600);

        // Draw border
        ctx.strokeStyle = '#D4AF37';
        ctx.lineWidth = 4;
        ctx.strokeRect(20, 20, 760, 560);

        // Draw text
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';

        ctx.font = 'bold 24px Arial';
        ctx.fillText('🦈 SHARK TANK SIMULATOR', 400, 80);

        ctx.font = 'bold 48px Arial';
        ctx.fillStyle = '#22c55e';
        ctx.fillText('DEAL!', 400, 160);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 36px Arial';
        ctx.fillText(currentDealData?.sharkName || 'Investor', 400, 280);

        ctx.font = '28px Arial';
        const amount = currentDealData?.offer?.amount || 0;
        const equity = currentDealData?.offer?.equity || 0;
        ctx.fillText(`$${amount.toLocaleString()} for ${equity}%`, 400, 340);

        ctx.font = '20px Arial';
        ctx.fillStyle = '#94a3b8';
        const valuation = equity > 0 ? Math.round(amount / (equity / 100)) : 0;
        ctx.fillText(`Valuation: $${valuation.toLocaleString()}`, 400, 400);

        ctx.fillText(pitchData?.companyName || 'Your Company', 400, 500);

        const link = document.createElement('a');
        link.download = `shark-tank-deal-${Date.now()}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
      }
    } catch (err) {
      console.error('Failed to download deal card:', err);
      alert('Failed to download image. Please try taking a screenshot instead.');
    }
  }

  function shareDealTwitter() {
    if (!currentDealData) return;

    const companyName = pitchData?.companyName || 'my company';
    const amount = currentDealData.offer?.amount || 0;
    const equity = currentDealData.offer?.equity || 0;
    const sharkName = currentDealData.sharkName || 'an investor';

    const tweetText = `🦈 I just closed a deal on Shark Tank Simulator!\n\n${sharkName} invested $${amount.toLocaleString()} for ${equity}% of ${companyName}!\n\nThink you can do better? Try it yourself 👇`;

    const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(window.location.href)}`;

    window.open(tweetUrl, '_blank', 'width=550,height=420');
  }

  function copyDealLink() {
    const companyName = pitchData?.companyName || 'company';
    const amount = currentDealData?.offer?.amount || 0;
    const equity = currentDealData?.offer?.equity || 0;

    const shareText = `🦈 Check out my Shark Tank Simulator deal: $${amount.toLocaleString()} for ${equity}% of ${companyName}! Try it at ${window.location.href}`;

    navigator.clipboard.writeText(shareText).then(() => {
      // Show feedback
      const btn = document.querySelector('.deal-card-btn--copy');
      if (btn) {
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span style="color: #22c55e;">✓ Copied!</span>';
        setTimeout(() => {
          btn.innerHTML = originalText;
        }, 2000);
      }
    }).catch(err => {
      console.error('Failed to copy:', err);
      alert('Failed to copy to clipboard');
    });
  }

  function showDealSummary() {
    // Stop everything
    stopTimer();
    stopWebcam();
    stopSpeechRecognition();
    disconnectSSE();

    // Show summary
    const pitchWords = (window.pitchTranscript || []).reduce((acc, t) => acc + t.text.split(' ').length, 0);
    const totalWords = transcript.reduce((acc, t) => acc + t.text.split(' ').length, 0);

    alert(`Session Complete!\n\nPitch: ${pitchWords} words\nTotal transcript: ${totalWords} words\n\nCongratulations on your deal!`);

    // Go back to entry form
    showView('entryView');

    // Reset state
    resetSession();
  }

  function endSession() {
    // Stop everything
    stopTimer();
    stopWebcam();
    stopSpeechRecognition();
    disconnectSSE();

    // Store final transcript
    window.fullTranscript = transcript;

    // Log summary
    console.log('Session ended.');
    console.log('Full transcript:', transcript);
    console.log('Pitch data:', pitchData);

    // Show summary
    const pitchWords = (window.pitchTranscript || []).reduce((acc, t) => acc + t.text.split(' ').length, 0);
    const totalWords = transcript.reduce((acc, t) => acc + t.text.split(' ').length, 0);

    alert(`Session Complete!\n\nPitch: ${pitchWords} words\nTotal: ${totalWords} words\nSegments: ${transcript.length}`);

    // Go back to entry form
    showView('entryView');

    // Reset state
    resetSession();
  }

  function resetSession() {
    transcript = [];
    remainingSeconds = TOTAL_SESSION_TIME;
    pitchTimeRemaining = PITCH_DURATION;
    currentPhase = 'pitch';
    sessionId = null;
    sharkStates = {};
    pendingOffers = [];
  }

  // ========================================
  // Timer
  // ========================================
  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  function updateTimerDisplay() {
    const timer = document.getElementById('timerDisplay');
    const pressureBar = document.getElementById('pressureBar');
    if (!timer) return;

    // During pitch phase, show pitch time remaining
    // After pitch, show total session time remaining
    if (currentPhase === 'pitch') {
      timer.textContent = formatTime(pitchTimeRemaining);

      // Pressure states based on pitch time
      let state = 'neutral';
      if (pitchTimeRemaining < 30) {
        state = 'critical';
      } else if (pitchTimeRemaining < 60) {
        state = 'warning';
      }
      timer.dataset.state = state;
      if (pressureBar) pressureBar.dataset.state = state;
    } else {
      timer.textContent = formatTime(remainingSeconds);
      timer.dataset.state = 'neutral';
      if (pressureBar) pressureBar.dataset.state = 'neutral';
    }
  }

  function startTimer() {
    // Clear any existing timer first
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Timer for pitch phase countdown
    console.log('[Timer] Starting timer - currentPhase:', currentPhase, 'pitchTimeRemaining:', pitchTimeRemaining);

    // Update display immediately
    updateTimerDisplay();

    // Only run pitch timer during pitch phase
    if (currentPhase === 'pitch') {
      console.log('[Timer] Starting 1-minute pitch countdown');
      timerInterval = setInterval(() => {
        pitchTimeRemaining--;
        updateTimerDisplay(); // Update the visual display
        console.log('[Timer] Pitch time remaining:', pitchTimeRemaining);
        if (pitchTimeRemaining <= 0) {
          clearInterval(timerInterval);
          timerInterval = null;
          console.log('[Timer] Pitch time up - transitioning to Q&A');
          endPitchPhase();
        }
      }, 1000);
    }
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  // Manual timer controls (exposed globally)
  function setTimer(timeStr) {
    const [mins, secs] = timeStr.split(':').map(Number);
    remainingSeconds = mins * 60 + secs;
    updateTimerDisplay();
  }

  function setTimerState(state) {
    const timer = document.getElementById('timerDisplay');
    const pressureBar = document.getElementById('pressureBar');
    if (timer) timer.dataset.state = state;
    if (pressureBar) pressureBar.dataset.state = state;
  }

  function setPressureState(state) {
    const pressureBar = document.getElementById('pressureBar');
    if (pressureBar) pressureBar.dataset.state = state;
  }

  // ========================================
  // Participants
  // ========================================
  function initParticipants() {
    const participants = document.querySelectorAll('.participant[data-investor]');

    participants.forEach(participant => {
      participant.addEventListener('click', () => cycleState(participant));
    });

    // Initialize confidence bars with current shark states
    initConfidenceBars();
  }

  function initConfidenceBars() {
    // Set initial confidence bar values from sharkStates
    Object.keys(sharkStates).forEach(sharkId => {
      const confidence = sharkStates[sharkId]?.confidence || 50;
      updateConfidenceBar(sharkId, confidence, 0);
    });

    // If no sharkStates yet, default all bars to 50%
    if (Object.keys(sharkStates).length === 0) {
      const bars = document.querySelectorAll('.confidence-bar');
      bars.forEach(bar => {
        bar.style.width = '50%';
        bar.classList.add('medium');
      });
    }
  }

  function cycleState(participant) {
    const currentState = participant.dataset.state;
    const currentIndex = STATES.indexOf(currentState);
    const nextIndex = (currentIndex + 1) % STATES.length;
    const nextState = STATES[nextIndex];
    
    participant.dataset.state = nextState;
    
    // Update video styling
    const video = participant.querySelector('.participant-video');
    video.classList.remove('participant-video--out', 'participant-video--interested');
    participant.classList.remove('participant--out');
    
    if (nextState === 'out') {
      video.classList.add('participant-video--out');
      participant.classList.add('participant--out');
    } else if (nextState === 'interested') {
      video.classList.add('participant-video--interested');
    }
    
    // Update badge
    const badge = participant.querySelector('.participant-badge');
    if (badge) {
      badge.classList.remove('badge--live', 'badge--interested', 'badge--out');
      badge.classList.add(`badge--${nextState}`);
      badge.textContent = nextState.toUpperCase();
    }
  }

  // ========================================
  // Tile Effects
  // ========================================
  function flashInterrupt(tileElement) {
    const video = tileElement.querySelector('.participant-video');
    if (!video) return;
    
    video.classList.add('interrupt');
    setTimeout(() => {
      video.classList.remove('interrupt');
    }, 120);
  }

  // ========================================
  // Chat Functions
  // ========================================
  function showThinking(sharkName) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return null;

    hideThinking(sharkName);

    const message = document.createElement('div');
    message.className = 'message message--thinking';
    message.dataset.thinkingShark = sharkName;
    message.innerHTML = `
      <div class="message-header">
        <span class="message-author">${sharkName}</span>
      </div>
      <p class="message-text">${sharkName} is thinking…</p>
    `;

    messagesContainer.appendChild(message);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return message;
  }

  function hideThinking(sharkName) {
    const existing = document.querySelector(`.message--thinking[data-thinking-shark="${sharkName}"]`);
    if (existing) existing.remove();
  }

  function sendSharkMessage(sharkName, text) {
    hideThinking(sharkName);

    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return null;

    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false 
    });

    const message = document.createElement('div');
    message.className = 'message';
    message.innerHTML = `
      <div class="message-header">
        <span class="message-author">${sharkName}</span>
        <span class="message-time">${time}</span>
      </div>
      <p class="message-text">${text}</p>
    `;

    messagesContainer.appendChild(message);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return message;
  }

  function sendSystemMessage(text) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return null;

    const message = document.createElement('div');
    message.className = 'message message--system';
    message.innerHTML = `<p class="message-text">${text}</p>`;

    messagesContainer.appendChild(message);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return message;
  }

  // ========================================
  // Global Exports
  // ========================================
  window.flashInterrupt = flashInterrupt;
  window.showThinking = showThinking;
  window.hideThinking = hideThinking;
  window.sendSharkMessage = sendSharkMessage;
  window.sendSystemMessage = sendSystemMessage;
  window.setTimer = setTimer;
  window.setTimerState = setTimerState;
  window.setPressureState = setPressureState;
  window.stopTimer = stopTimer;
  window.startTimer = startTimer;
  window.showView = showView;
  window.endPitchPhase = endPitchPhase;
  window.endSession = endSession;
  window.getCurrentPhase = () => currentPhase;
  window.getTranscript = () => transcript;

  // Offer handling exports
  window.acceptOffer = acceptOffer;
  window.declineOffer = declineOffer;
  window.showCounterModal = showCounterModal;
  window.hideCounterModal = hideCounterModal;
  window.replyToShark = replyToShark;
  window.submitCounterOffer = submitCounterOffer;
  window.getSessionId = () => sessionId;
  window.getSharkStates = () => sharkStates;

  // Transcript panel
  window.toggleTranscript = toggleTranscript;

  // Deal card sharing
  window.showDealCard = showDealCard;
  window.closeDealCard = closeDealCard;
  window.downloadDealCard = downloadDealCard;
  window.shareDealTwitter = shareDealTwitter;
  window.copyDealLink = copyDealLink;

  // ========================================
  // Initialize
  // ========================================
  function init() {
    initEntryForm();
    initCreditsSystem();
    initAuth();
    // Show auth view first (users can sign in or try free)
    showView('authView');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
