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
  // TODO: Replace with your actual Railway URL after deployment
  const RAILWAY_BACKEND_URL = 'https://shark-tank-simulator-production.up.railway.app';
  const API_BASE = isProduction ? RAILWAY_BACKEND_URL : window.location.origin;

  const TOTAL_SESSION_TIME = 900; // 15 minutes total
  const PITCH_DURATION = 180; // 3 minutes max for pitch
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
    'marcus_kellan': 'Marcus Kellan',
    'elena_brooks': 'Elena Brooks',
    'victor_slate': 'Victor Slate',
    'daniel_frost': 'Daniel Frost',
    'richard_hale': 'Richard Hale'
  };

  // ========================================
  // Auth State
  // ========================================
  let currentUser = null;
  let isGuest = false;
  let firebaseReady = false;

  function initAuth() {
    // Wait for Firebase to be ready
    if (window.firebaseAuth) {
      setupAuthListeners();
    } else {
      window.addEventListener('firebase-ready', setupAuthListeners);
    }
  }

  function setupAuthListeners() {
    firebaseReady = true;
    const { onAuthChange } = window.firebaseAuth;

    // Listen for auth state changes
    onAuthChange((user, twitterHandle) => {
      currentUser = user;
      updateAuthUI();

      // If user just logged in and we're on auth view, go to entry form
      if (user && document.getElementById('authView').style.display !== 'none') {
        showView('entryView');
      }
    });

    // Set up auth button listeners
    setupAuthButtons();
  }

  function setupAuthButtons() {
    // Twitter login button
    const twitterLoginBtn = document.getElementById('twitterLoginBtn');
    if (twitterLoginBtn) {
      twitterLoginBtn.addEventListener('click', async () => {
        try {
          twitterLoginBtn.disabled = true;
          twitterLoginBtn.textContent = 'Signing in...';
          await window.firebaseAuth.signInWithTwitter();
          // onAuthChange will handle the redirect
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
        isGuest = true;
        currentUser = null;
        showView('entryView');
        updateAuthUI();
      });
    }

    // Logout button (entry view)
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        try {
          await window.firebaseAuth.signOutUser();
          currentUser = null;
          isGuest = false;
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
        if (currentUser || isGuest) {
          showView('entryView');
        } else {
          showView('authView');
        }
      });
    }

    // Back to Auth button (entry view)
    const backToAuthBtn = document.getElementById('backToAuthBtn');
    if (backToAuthBtn) {
      backToAuthBtn.addEventListener('click', async () => {
        // If logged in, sign out first
        if (currentUser && window.firebaseAuth) {
          await window.firebaseAuth.signOutUser();
          currentUser = null;
        }
        isGuest = false;
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

      // DEMO MODE: Guests get a pre-scripted demo instead of real AI sharks
      if (isGuest) {
        isDemoMode = true;
        // Use demo pitch data instead of user input
        pitchData = { ...DEMO_SCRIPT.pitchData };
        window.pitchData = pitchData;

        // After transition, show demo panel (no backend calls)
        setTimeout(() => {
          showView('panelView');
          initDemoPanel();
        }, 2500);
        return;
      }

      // AUTHENTICATED USERS: Real AI shark experience
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

    // Skip button (dev/testing)
    const skipBtn = document.getElementById('skipBtn');
    if (skipBtn) {
      skipBtn.addEventListener('click', () => {
        // Use dummy data
        pitchData = {
          companyName: 'Test Company',
          amountRaising: 500000,
          equityPercent: 10,
          companyDescription: 'A test company for development purposes.',
          whyNow: 'Testing the panel flow.',
          proofType: 'idea',
          proofValue: null,
          expectedPushback: null
        };
        window.pitchData = pitchData;

        // Skip transition, go directly to panel
        showView('panelView');
        initPanel();
      });
    }
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
          // Clean up demo and go to auth
          cleanupDemo();
          showView('authView');
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
      showView('authView');
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

    // Initialize TTS audio player
    initAudioPlayer();

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

      default:
        console.log('Unknown SSE event type:', event.type);
    }
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
    const allParticipants = document.querySelectorAll('[data-investor]');
    let allOut = true;

    allParticipants.forEach(p => {
      const video = p.querySelector('.participant-video');
      if (!video.classList.contains('participant-video--out')) {
        allOut = false;
      }
    });

    if (allOut) {
      // All sharks are out - show sad ending
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
    const endBtn = document.getElementById('endPitchBtn');
    if (endBtn) {
      endBtn.addEventListener('click', endPitchPhase);
    }
  }

  async function endPitchPhase() {
    if (currentPhase === 'pitch') {
      // Transition from pitch to Q&A
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
      showDealSummary();
    } else {
      // End the entire session
      endSession();
    }
  }

  // ========================================
  // Offer Handling
  // ========================================
  function addOfferToUI(offer) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    pendingOffers.push(offer);

    const offerCard = document.createElement('div');
    offerCard.className = 'offer-card';
    offerCard.dataset.offerId = offer.id;

    let termsHtml = `<span class="offer-amount">$${offer.amount.toLocaleString()}</span>
                     <span class="offer-for">for</span>
                     <span class="offer-equity">${offer.equity}%</span>`;

    if (offer.royalty) {
      termsHtml += `<span class="offer-royalty">+ $${offer.royalty}/unit until $${offer.royaltyUntil?.toLocaleString() || offer.amount.toLocaleString()} recouped</span>`;
    }

    if (offer.conditions && offer.conditions.length > 0) {
      termsHtml += `<span class="offer-conditions">${offer.conditions.join(', ')}</span>`;
    }

    offerCard.innerHTML = `
      <div class="offer-header">
        <span class="offer-shark">${offer.sharkName}</span>
        <span class="offer-badge">OFFER</span>
      </div>
      <div class="offer-terms">
        ${termsHtml}
      </div>
      <div class="offer-actions">
        <button class="offer-btn offer-btn--accept" onclick="window.acceptOffer('${offer.id}')">Accept</button>
        <button class="offer-btn offer-btn--counter" onclick="window.showCounterModal('${offer.id}')">Counter</button>
        <button class="offer-btn offer-btn--decline" onclick="window.declineOffer('${offer.id}')">Decline</button>
      </div>
    `;

    messagesContainer.appendChild(offerCard);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  async function acceptOffer(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    // Disable offer buttons
    const offerCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (offerCard) {
      offerCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
    }

    sendSystemMessage(`You accepted ${offer.sharkName}'s offer!`);

    if (sessionId) {
      try {
        await fetch(`${API_BASE}/api/session/${sessionId}/offer-response`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ offerId, action: 'accept' })
        });
      } catch (err) {
        console.log('Failed to send acceptance to backend');
      }
    }
  }

  async function declineOffer(offerId) {
    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    // Disable offer buttons
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

    // Set current values
    document.getElementById('counterAmount').value = offer.amount;
    document.getElementById('counterEquity').value = Math.max(offer.equity - 5, 1);
    document.getElementById('counterOfferId').value = offerId;
    document.getElementById('counterSharkName').textContent = offer.sharkName;

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

    hideCounterModal();

    const offer = pendingOffers.find(o => o.id === offerId);
    if (!offer) return;

    // Disable offer buttons
    const offerCard = document.querySelector(`[data-offer-id="${offerId}"]`);
    if (offerCard) {
      offerCard.querySelectorAll('.offer-btn').forEach(btn => btn.disabled = true);
    }

    sendUserMessage(`Counter offer to ${offer.sharkName}: $${amount.toLocaleString()} for ${equity}%`);

    if (sessionId) {
      try {
        await fetch(`${API_BASE}/api/session/${sessionId}/offer-response`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            offerId,
            action: 'counter',
            counterTerms: { amount, equity }
          })
        });
      } catch (err) {
        console.log('Failed to send counter to backend');
      }
    }
  }

  function showDealClosed(data) {
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

    // Show success overlay
    const overlay = document.createElement('div');
    overlay.className = 'ending-overlay ending-overlay--success';
    overlay.innerHTML = `
      <div class="ending-content">
        <div class="ending-icon">🎉</div>
        <h2 class="ending-title">DEAL!</h2>
        <p class="ending-subtitle">Congratulations! You got a deal!</p>
        <div class="deal-details">
          <div class="deal-shark">${data.sharkName}</div>
          <div class="deal-terms">
            <span class="deal-amount">$${offer.amount.toLocaleString()}</span>
            <span class="deal-for">for</span>
            <span class="deal-equity">${offer.equity}%</span>
          </div>
          ${offer.royalty ? `<div class="deal-royalty">+ $${offer.royalty}/unit royalty</div>` : ''}
        </div>
        <button class="ending-btn" onclick="location.reload()">New Pitch</button>
      </div>
    `;
    document.body.appendChild(overlay);
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
    updateTimerDisplay();

    timerInterval = setInterval(() => {
      remainingSeconds--;

      // During pitch, also count down pitch time
      if (currentPhase === 'pitch') {
        pitchTimeRemaining--;

        // Auto-end pitch if pitch time runs out
        if (pitchTimeRemaining <= 0) {
          endPitchPhase();
          return;
        }
      }

      updateTimerDisplay();

      if (remainingSeconds <= 0) {
        clearInterval(timerInterval);
        sendSystemMessage('Time is up! The session has ended.');
        endSession();
      }
    }, 1000);
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
  window.submitCounterOffer = submitCounterOffer;
  window.getSessionId = () => sessionId;
  window.getSharkStates = () => sharkStates;

  // Transcript panel
  window.toggleTranscript = toggleTranscript;

  // ========================================
  // Initialize
  // ========================================
  function init() {
    initEntryForm();
    initAuth();
    // Auth view is shown by default now
    showView('authView');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
