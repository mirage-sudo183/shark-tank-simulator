/**
 * Shark Tank Simulator — Minimal UI Interactions
 * Click investor tiles to cycle through states: LIVE → INTERESTED → OUT
 */

(function() {
  'use strict';

  const STATES = ['live', 'interested', 'out'];

  /**
   * Briefly flash an interrupt effect on a tile (120ms)
   * @param {HTMLElement} tileElement - The participant tile element
   */
  function flashInterrupt(tileElement) {
    const video = tileElement.querySelector('.participant-video');
    if (!video) return;
    
    video.classList.add('interrupt');
    setTimeout(() => {
      video.classList.remove('interrupt');
    }, 120);
  }

  // Expose to global scope for external use
  window.flashInterrupt = flashInterrupt;

  /**
   * Show a "thinking" placeholder message for a shark
   * @param {string} sharkName - The shark's display name
   * @returns {HTMLElement} The thinking message element
   */
  function showThinking(sharkName) {
    const messagesContainer = document.querySelector('.chat-messages');
    if (!messagesContainer) return null;

    // Remove any existing thinking message from this shark
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

  /**
   * Hide a shark's thinking placeholder
   * @param {string} sharkName - The shark's display name
   */
  function hideThinking(sharkName) {
    const existing = document.querySelector(`.message--thinking[data-thinking-shark="${sharkName}"]`);
    if (existing) {
      existing.remove();
    }
  }

  /**
   * Send a real message from a shark (removes thinking state)
   * @param {string} sharkName - The shark's display name
   * @param {string} text - The message text
   * @returns {HTMLElement} The new message element
   */
  function sendSharkMessage(sharkName, text) {
    // Remove thinking placeholder
    hideThinking(sharkName);

    const messagesContainer = document.querySelector('.chat-messages');
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

  // Expose chat functions
  window.showThinking = showThinking;
  window.hideThinking = hideThinking;
  window.sendSharkMessage = sendSharkMessage;

  /**
   * Set the timer display value and auto-detect state based on time
   * @param {string} timeStr - Time string in MM:SS format (e.g., "02:45")
   */
  function setTimer(timeStr) {
    const timer = document.querySelector('.timer');
    const pressureBar = document.querySelector('.pressure-bar');
    if (!timer) return;

    timer.textContent = timeStr;

    // Parse minutes and seconds
    const [mins, secs] = timeStr.split(':').map(Number);
    const totalSeconds = mins * 60 + secs;

    // Determine state
    let state = 'neutral';
    if (totalSeconds < 60) {
      state = 'critical';
    } else if (totalSeconds < 180) {
      state = 'warning';
    }

    timer.dataset.state = state;
    if (pressureBar) {
      pressureBar.dataset.state = state;
    }
  }

  /**
   * Manually set timer state (overrides auto-detection)
   * @param {string} state - 'neutral', 'warning', or 'critical'
   */
  function setTimerState(state) {
    const timer = document.querySelector('.timer');
    const pressureBar = document.querySelector('.pressure-bar');
    
    if (timer) timer.dataset.state = state;
    if (pressureBar) pressureBar.dataset.state = state;
  }

  /**
   * Set pressure bar state independently
   * @param {string} state - 'neutral', 'warning', or 'critical'
   */
  function setPressureState(state) {
    const pressureBar = document.querySelector('.pressure-bar');
    if (pressureBar) pressureBar.dataset.state = state;
  }

  // Expose timer functions
  window.setTimer = setTimer;
  window.setTimerState = setTimerState;
  window.setPressureState = setPressureState;

  /**
   * Cycle participant state on click
   */
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
    
    // Update status indicator
    const status = participant.querySelector('.participant-status');
    status.classList.remove('status--live', 'status--interested', 'status--out');
    status.classList.add(`status--${nextState}`);
  }

  /**
   * Initialize
   */
  function init() {
    const participants = document.querySelectorAll('.participant[data-investor]');
    
    participants.forEach(participant => {
      participant.addEventListener('click', () => cycleState(participant));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
