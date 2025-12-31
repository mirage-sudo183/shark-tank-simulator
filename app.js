/**
 * Shark Tank Simulator
 * Entry form → Transition → Live investor panel
 */

(function() {
  'use strict';

  // ========================================
  // State
  // ========================================
  const STATES = ['live', 'interested', 'out'];
  const PHASES = ['pitch', 'negotiation'];
  let pitchData = null;
  let timerInterval = null;
  let remainingSeconds = 600; // 10 minutes
  let mediaStream = null;
  let recognition = null;
  let transcript = [];
  let isListening = false;
  let currentPhase = 'pitch';

  // ========================================
  // View Management
  // ========================================
  function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.style.display = 'none');
    const view = document.getElementById(viewId);
    if (view) view.style.display = 'flex';
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
      });
    }

    // Form submission
    form.addEventListener('submit', (e) => {
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

      // Store for later use
      window.pitchData = pitchData;

      // Show transition
      showView('transitionView');

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
  // Panel Initialization
  // ========================================
  function initPanel() {
    // Update meeting title with company name
    const meetingTitle = document.getElementById('meetingTitle');
    if (meetingTitle && pitchData) {
      meetingTitle.textContent = `${pitchData.companyName} — Series A Pitch`;
    }

    // Initialize participants
    initParticipants();

    // Start timer immediately
    remainingSeconds = 600;
    startTimer();

    // Initialize webcam
    initWebcam();

    // Initialize speech recognition
    initSpeechRecognition();

    // Initialize end pitch button
    initEndPitch();
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
  // Speech Recognition
  // ========================================
  const ENABLE_SPEECH_RECOGNITION = true; // Enabled - requires HTTPS

  function initSpeechRecognition() {
    if (!ENABLE_SPEECH_RECOGNITION) {
      console.log('Speech recognition disabled (requires HTTPS in production)');
      hideCaptionArea();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.log('Speech recognition not supported');
      hideCaptionArea();
      return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      showListeningIndicator(true);
    };

    let shouldRestart = true;

    recognition.onend = () => {
      isListening = false;
      showListeningIndicator(false);
      // Restart if still in panel and no fatal error occurred
      if (shouldRestart && document.getElementById('panelView').style.display !== 'none') {
        setTimeout(() => {
          try {
            recognition.start();
          } catch (e) {
            // Already started or other error
          }
        }, 100);
      }
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
          // Store final transcript
          transcript.push({
            text: result[0].transcript.trim(),
            timestamp: Date.now(),
            timeRemaining: remainingSeconds
          });
        } else {
          interimTranscript += result[0].transcript;
        }
      }

      // Update caption with current speech
      const displayText = finalTranscript || interimTranscript || 'Listening...';
      updateCaption(displayText);
    };

    recognition.onerror = (event) => {
      console.log('Speech recognition error:', event.error);
      
      switch (event.error) {
        case 'no-speech':
          updateCaption('Waiting for you to speak...');
          break;
        case 'network':
          shouldRestart = false;
          hideCaptionArea();
          sendSystemMessage('Live transcription unavailable — pitch when ready!');
          break;
        case 'not-allowed':
        case 'service-not-allowed':
          shouldRestart = false;
          hideCaptionArea();
          break;
        case 'audio-capture':
          shouldRestart = false;
          hideCaptionArea();
          break;
        case 'aborted':
          // User or system aborted, don't show error
          break;
        default:
          updateCaption('Continuing without live transcription');
          showListeningIndicator(false);
      }
    };

    // Start recognition
    try {
      recognition.start();
    } catch (e) {
      console.log('Could not start speech recognition:', e);
    }
  }

  function stopSpeechRecognition() {
    if (recognition) {
      try {
        recognition.stop();
      } catch (e) {
        // Already stopped
      }
      recognition = null;
    }
    isListening = false;
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

  function endPitchPhase() {
    if (currentPhase === 'pitch') {
      // Transition from pitch to negotiation
      currentPhase = 'negotiation';
      
      // Store pitch transcript and time used
      window.pitchTranscript = [...transcript];
      window.pitchTimeUsed = 600 - remainingSeconds;
      
      // Update UI for negotiation phase
      const endBtn = document.getElementById('endPitchBtn');
      if (endBtn) {
        endBtn.textContent = 'Leave Panel';
        endBtn.classList.add('leave-btn--final');
      }

      // Update caption
      updateCaption('Q&A with the investors has begun...');

      // Send system message
      sendSystemMessage('The pitch has ended. Investors may now ask questions.');

      // Timer keeps running - no changes needed, it continues counting down
      // Reset timer state to neutral for Q&A (less pressure)
      const timerDisplay = document.getElementById('timerDisplay');
      if (timerDisplay) {
        timerDisplay.dataset.state = 'neutral';
      }
      
      const pressureBar = document.getElementById('pressureBar');
      if (pressureBar) {
        pressureBar.dataset.state = 'neutral';
      }

      // Add phase indicator
      const meetingTitle = document.getElementById('meetingTitle');
      if (meetingTitle && pitchData) {
        meetingTitle.textContent = `${pitchData.companyName} — Negotiation`;
      }

      console.log('Pitch phase ended. Entering negotiation phase.');
      console.log('Pitch transcript:', window.pitchTranscript);

    } else {
      // End the entire session
      endSession();
    }
  }

  function endSession() {
    // Stop everything
    stopTimer();
    stopWebcam();
    stopSpeechRecognition();

    // Store final transcript
    window.fullTranscript = transcript;

    // Log summary
    console.log('Session ended.');
    console.log('Full transcript:', transcript);
    console.log('Pitch data:', pitchData);

    // Show summary
    const pitchWords = (window.pitchTranscript || []).reduce((acc, t) => acc + t.text.split(' ').length, 0);
    const totalWords = transcript.reduce((acc, t) => acc + t.text.split(' ').length, 0);
    
    alert(`Session Complete!\n\nPitch transcript: ${pitchWords} words\nTotal transcript: ${totalWords} words\nTranscript segments: ${transcript.length}`);

    // Go back to entry form
    showView('entryView');
    
    // Reset state
    transcript = [];
    remainingSeconds = 600;
    currentPhase = 'pitch';
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

    timer.textContent = formatTime(remainingSeconds);

    // Only apply pressure states during pitch phase
    if (currentPhase === 'pitch') {
      let state = 'neutral';
      if (remainingSeconds < 60) {
        state = 'critical';
      } else if (remainingSeconds < 180) {
        state = 'warning';
      }
      timer.dataset.state = state;
      if (pressureBar) pressureBar.dataset.state = state;
    }
  }

  function startTimer() {
    updateTimerDisplay();
    
    timerInterval = setInterval(() => {
      remainingSeconds--;
      updateTimerDisplay();
      
      if (remainingSeconds <= 0) {
        clearInterval(timerInterval);
        // Time's up handling could go here
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

  // ========================================
  // Initialize
  // ========================================
  function init() {
    initEntryForm();
    // Entry view is shown by default
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
