"""
Shark Tank Simulator - Flask Backend
Handles AI shark responses, session management, and SSE streaming
"""

import os
import json
import uuid
import queue
import threading
import tempfile
import subprocess
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from session import SessionManager
from sharks import SharkManager, SHARK_IDS
from ai_client import AIClient
from tts_client import TTSClient
from firebase_admin_init import initialize_firebase, optional_auth, require_auth

# Verification modules
from verification.defillama import search_protocols, verify_protocol_ownership
from verification.trustmrr import verify_mrr_ownership

# Rate limiting
from rate_limiter import rate_limiter, rate_limit

# OpenAI for Whisper transcription
try:
    from openai import OpenAI
    openai_client = None
except ImportError:
    OpenAI = None
    openai_client = None

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='..', static_url_path='')

# CORS configuration - allow frontend domains
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Initialize managers
session_manager = SessionManager()
shark_manager = SharkManager()

# Log API key status (for debugging)
# Strip whitespace/newlines from API key (common copy-paste issue)
anthropic_key = os.getenv('ANTHROPIC_API_KEY')
if anthropic_key:
    anthropic_key = anthropic_key.strip()
    print(f"[AI] Anthropic API key configured (length: {len(anthropic_key)})")
else:
    print("[AI] WARNING: ANTHROPIC_API_KEY not set - using fallback responses!")

ai_client = AIClient(api_key=anthropic_key)
tts_client = TTSClient(api_key=os.getenv('ELEVEN_LABS_API_KEY'))

# Initialize OpenAI client for Whisper
if OpenAI and os.getenv('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    print("[Whisper] OpenAI client initialized for speech-to-text")
else:
    print("[Whisper] OpenAI API key not configured - speech-to-text disabled")

# Initialize Firebase Admin SDK
initialize_firebase()

# SSE event queues per session
session_queues = {}
# Track recently sent messages to prevent duplicates
recent_messages = {}


def get_session_queue(session_id):
    """Get or create an event queue for a session."""
    if session_id not in session_queues:
        session_queues[session_id] = queue.Queue()
    return session_queues[session_id]


def send_sse_event(session_id, event_type, data):
    """Send an SSE event to a session with deduplication."""
    # Create a unique ID for shark_message events to prevent duplicates
    if event_type == 'shark_message':
        msg_key = f"{session_id}-{data.get('sharkId', '')}-{data.get('text', '')[:50]}"
        if session_id not in recent_messages:
            recent_messages[session_id] = set()
        if msg_key in recent_messages[session_id]:
            print(f"[SSE] Duplicate message blocked: {msg_key[:60]}...")
            return  # Skip duplicate
        recent_messages[session_id].add(msg_key)
        # Keep set from growing too large
        if len(recent_messages[session_id]) > 50:
            recent_messages[session_id] = set(list(recent_messages[session_id])[-25:])

    q = get_session_queue(session_id)
    event = {
        'type': event_type,
        'data': data,
        'timestamp': int(__import__('time').time() * 1000)
    }
    q.put(event)


# =============================================================================
# Health Check (for Railway/Docker)
# =============================================================================

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'shark-tank-simulator'})


@app.route('/api/debug/ai-status')
def ai_status():
    """Debug endpoint to check AI client status."""
    import socket
    import urllib.request

    status = {
        'anthropic_key_set': bool(anthropic_key),
        'anthropic_key_length': len(anthropic_key) if anthropic_key else 0,
        'client_initialized': ai_client.client is not None,
    }

    # Test DNS resolution
    try:
        ip = socket.gethostbyname('api.anthropic.com')
        status['dns_resolution'] = f'success: {ip}'
    except Exception as e:
        status['dns_resolution'] = f'failed: {e}'

    # Test basic HTTPS connectivity
    try:
        req = urllib.request.Request('https://api.anthropic.com/', method='HEAD')
        req.add_header('User-Agent', 'shark-tank-simulator/1.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            status['https_connectivity'] = f'success: {resp.status}'
    except Exception as e:
        status['https_connectivity'] = f'failed: {type(e).__name__}: {str(e)[:100]}'

    # Test with httpx directly - POST request like Anthropic SDK
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': anthropic_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 10,
                    'messages': [{'role': 'user', 'content': 'Say OK'}]
                }
            )
            status['httpx_post_test'] = f'status: {resp.status_code}'
            if resp.status_code == 200:
                status['httpx_response'] = resp.json().get('content', [{}])[0].get('text', '')[:50]
            else:
                status['httpx_error'] = resp.text[:200]
    except Exception as e:
        status['httpx_post_test'] = f'failed: {type(e).__name__}: {str(e)[:150]}'

    # Try a simple API call to test connectivity
    if ai_client.client:
        try:
            # Use a minimal request to test connection
            response = ai_client.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            status['api_test'] = 'success'
            status['api_response'] = response.content[0].text[:50]
        except Exception as e:
            import traceback
            status['api_test'] = 'failed'
            status['api_error'] = f"{type(e).__name__}: {str(e)[:200]}"
            status['api_traceback'] = traceback.format_exc()[-500:]

    return jsonify(status)


# =============================================================================
# Static File Serving
# =============================================================================

@app.route('/')
def index():
    return send_from_directory('..', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('..', path)


# =============================================================================
# Session Management
# =============================================================================

@app.route('/api/session/start', methods=['POST'])
@optional_auth
@rate_limit
def start_session():
    """Initialize a new pitch session."""
    data = request.json
    pitch_data = data.get('pitchData', {})
    verification = data.get('verification')

    # Extract user info if authenticated
    user_id = None
    twitter_handle = None
    if hasattr(request, 'user') and request.user:
        user_id = request.user.get('uid')
        if hasattr(request, 'user_data') and request.user_data:
            twitter_handle = request.user_data.get('twitterHandle')

    # Create session with user info and verification
    session_id = session_manager.create_session(pitch_data, user_id=user_id, twitter_handle=twitter_handle)

    # Initialize shark states with confidence scores
    sharks = []
    for shark_id in SHARK_IDS:
        confidence = shark_manager.calculate_initial_confidence(shark_id, pitch_data)
        shark_state = {
            'id': shark_id,
            'name': shark_manager.get_shark_name(shark_id),
            'status': 'live',
            'confidence': confidence,
            'isSpeaking': False,
            'hasOffered': False,
            'currentOffer': None
        }
        session_manager.update_shark_state(session_id, shark_id, shark_state)
        sharks.append(shark_state)

    return jsonify({
        'sessionId': session_id,
        'sharks': sharks
    })


@app.route('/api/session/<session_id>/pitch-complete', methods=['POST'])
def pitch_complete(session_id):
    """Submit pitch transcript for AI analysis."""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.json
    transcript = data.get('transcript', [])
    pitch_duration = data.get('pitchDuration', 180)

    # Store transcript
    session_manager.set_transcript(session_id, transcript)
    session_manager.set_phase(session_id, 'qa')

    # Update confidence based on transcript
    confidence_scores = {}
    for shark_id in SHARK_IDS:
        current = session_manager.get_shark_state(session_id, shark_id)
        new_confidence = shark_manager.update_confidence_from_transcript(
            shark_id,
            transcript,
            current.get('confidence', 50)
        )
        session_manager.update_shark_state(session_id, shark_id, {'confidence': new_confidence})
        confidence_scores[shark_id] = new_confidence

    # Start generating initial reactions in background
    threading.Thread(
        target=generate_initial_reactions,
        args=(session_id,),
        daemon=True
    ).start()

    return jsonify({
        'confidenceScores': confidence_scores,
        'phase': 'qa'
    })


def generate_initial_reactions(session_id):
    """Generate initial shark reaction after pitch - ONE shark only."""
    session = session_manager.get_session(session_id)
    if not session:
        return

    pitch_data = session.get('pitchData', {})
    transcript = session.get('transcript', [])

    # Determine speaking order based on confidence (higher confidence speaks first)
    shark_states = []
    for shark_id in SHARK_IDS:
        state = session_manager.get_shark_state(session_id, shark_id)
        if state.get('status') != 'out':
            shark_states.append((shark_id, state.get('confidence', 50)))

    # Sort by confidence descending
    shark_states.sort(key=lambda x: x[1], reverse=True)

    # Only ONE shark responds initially, then waits for user
    for i, (shark_id, confidence) in enumerate(shark_states[:1]):
        # Send thinking indicator
        send_sse_event(session_id, 'shark_thinking', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id)
        })

        # Check if should go out
        if shark_manager.should_go_out(shark_id, confidence, 'qa', {}):
            out_reason = shark_manager.get_out_reason(shark_id)
            session_manager.update_shark_state(session_id, shark_id, {'status': 'out'})
            send_sse_event(session_id, 'shark_out', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'message': out_reason
            })
            continue

        # Generate response
        response = ai_client.generate_shark_response(
            shark_id=shark_id,
            persona=shark_manager.get_persona(shark_id),
            pitch_data=pitch_data,
            transcript=transcript,
            context=session.get('qaTranscript', []),
            confidence=confidence
        )

        if response:
            # Check if shark is going out (detect "I'm out" in response)
            is_going_out = "i'm out" in response.lower() or "im out" in response.lower()

            # Check if response contains an offer (only if not going out)
            offer = shark_manager.parse_offer_from_response(shark_id, response, pitch_data) if not is_going_out else None

            # Send speaking indicator
            send_sse_event(session_id, 'shark_speaking', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'speaking': True
            })

            # Synthesize TTS audio
            tts_result = tts_client.synthesize_for_shark(shark_id, response)

            # Send message with audio
            send_sse_event(session_id, 'shark_message', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'text': response,
                'offer': offer,
                'audio': tts_result if tts_result.get('audioData') else None,
                'duration': tts_result.get('duration', 0)
            })

            # If shark said "I'm out", mark them as out
            if is_going_out:
                session_manager.update_shark_state(session_id, shark_id, {'status': 'out'})
                send_sse_event(session_id, 'shark_out', {
                    'sharkId': shark_id,
                    'sharkName': shark_manager.get_shark_name(shark_id),
                    'message': response
                })

            # If there's an offer, send it separately
            if offer:
                session_manager.add_offer(session_id, offer)
                send_sse_event(session_id, 'shark_offer', {
                    'sharkId': shark_id,
                    'sharkName': shark_manager.get_shark_name(shark_id),
                    'offer': offer
                })

            # Store in QA transcript
            session_manager.add_qa_message(session_id, {
                'speaker': shark_manager.get_shark_name(shark_id),
                'speakerId': shark_id,
                'text': response,
                'isShark': True
            })

            # Done speaking
            send_sse_event(session_id, 'shark_speaking', {
                'sharkId': shark_id,
                'speaking': False
            })

        # Small delay between sharks
        import time
        time.sleep(1)


@app.route('/api/session/<session_id>/stream')
def stream_events(session_id):
    """SSE endpoint for real-time shark responses."""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    def generate():
        q = get_session_queue(session_id)

        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'sessionId': session_id})}\n\n"

        while True:
            try:
                # Wait for events with timeout
                event = q.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Send heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/session/<session_id>/user-message', methods=['POST'])
def user_message(session_id):
    """User sends a message during Q&A."""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.json
    text = data.get('text', '')

    if not text:
        return jsonify({'error': 'Message text required'}), 400

    # Store user message
    session_manager.add_qa_message(session_id, {
        'speaker': 'You',
        'speakerId': 'user',
        'text': text,
        'isShark': False
    })

    # Generate shark responses in background
    threading.Thread(
        target=generate_shark_responses_to_user,
        args=(session_id, text),
        daemon=True
    ).start()

    return jsonify({'received': True})


def generate_shark_responses_to_user(session_id, user_message):
    """Generate ONE shark response to user message - conversational flow."""
    session = session_manager.get_session(session_id)
    if not session:
        return

    pitch_data = session.get('pitchData', {})
    transcript = session.get('transcript', [])
    context = session.get('qaTranscript', [])

    # Pick ONE shark to respond - rotate through sharks who haven't spoken recently
    responding_sharks = []
    for shark_id in SHARK_IDS:
        state = session_manager.get_shark_state(session_id, shark_id)
        if state.get('status') != 'out':
            responding_sharks.append((shark_id, state.get('confidence', 50)))

    if not responding_sharks:
        return

    # Find who spoke last and pick someone different
    last_speaker = None
    for msg in reversed(context):
        if msg.get('isShark'):
            last_speaker = msg.get('speakerId')
            break

    # Filter out last speaker, or pick randomly if all have spoken
    import random
    candidates = [(s, c) for s, c in responding_sharks if s != last_speaker]
    if not candidates:
        candidates = responding_sharks

    # Pick one shark (weighted by confidence)
    shark_id, confidence = random.choice(candidates)

    # Only one shark responds
    for shark_id, confidence in [(shark_id, confidence)]:
        # Thinking indicator
        send_sse_event(session_id, 'shark_thinking', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id)
        })

        # Generate response
        response = ai_client.generate_shark_response(
            shark_id=shark_id,
            persona=shark_manager.get_persona(shark_id),
            pitch_data=pitch_data,
            transcript=transcript,
            context=context,
            confidence=confidence,
            user_message=user_message
        )

        if response:
            # Check if shark is going out (detect "I'm out" in response)
            is_going_out = "i'm out" in response.lower() or "im out" in response.lower()

            # Check for offer
            offer = shark_manager.parse_offer_from_response(shark_id, response, pitch_data) if not is_going_out else None

            # Speaking
            send_sse_event(session_id, 'shark_speaking', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'speaking': True
            })

            # Synthesize TTS audio
            tts_result = tts_client.synthesize_for_shark(shark_id, response)

            # Message with audio
            send_sse_event(session_id, 'shark_message', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'text': response,
                'offer': offer,
                'audio': tts_result if tts_result.get('audioData') else None,
                'duration': tts_result.get('duration', 0)
            })

            # If shark said "I'm out", mark them as out
            if is_going_out:
                session_manager.update_shark_state(session_id, shark_id, {'status': 'out'})
                send_sse_event(session_id, 'shark_out', {
                    'sharkId': shark_id,
                    'sharkName': shark_manager.get_shark_name(shark_id),
                    'message': response
                })

            if offer:
                session_manager.add_offer(session_id, offer)
                send_sse_event(session_id, 'shark_offer', {
                    'sharkId': shark_id,
                    'sharkName': shark_manager.get_shark_name(shark_id),
                    'offer': offer
                })

            # Store
            session_manager.add_qa_message(session_id, {
                'speaker': shark_manager.get_shark_name(shark_id),
                'speakerId': shark_id,
                'text': response,
                'isShark': True
            })

            # Done speaking
            send_sse_event(session_id, 'shark_speaking', {
                'sharkId': shark_id,
                'speaking': False
            })

        import time
        time.sleep(0.5)


@app.route('/api/session/<session_id>/offer-response', methods=['POST'])
def offer_response(session_id):
    """User responds to an offer (accept/decline/counter)."""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.json
    offer_id = data.get('offerId')
    action = data.get('action')  # 'accept', 'decline', 'counter'
    counter_terms = data.get('counterTerms')

    if action == 'accept':
        # Deal closed!
        offer = session_manager.get_offer(session_id, offer_id)
        if offer:
            session_manager.set_phase(session_id, 'closed')
            session_manager.set_final_deal(session_id, offer)

            shark_id = offer.get('sharkId')
            send_sse_event(session_id, 'deal_closed', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'offer': offer
            })

            return jsonify({'result': 'deal_closed', 'offer': offer})

    elif action == 'decline':
        offer = session_manager.get_offer(session_id, offer_id)
        if offer:
            session_manager.update_offer_status(session_id, offer_id, 'declined')
            shark_id = offer.get('sharkId')

            # Shark might go out or make new offer
            threading.Thread(
                target=handle_offer_decline,
                args=(session_id, shark_id, offer),
                daemon=True
            ).start()

            return jsonify({'result': 'declined'})

    elif action == 'counter':
        offer = session_manager.get_offer(session_id, offer_id)
        if offer and counter_terms:
            session_manager.update_offer_status(session_id, offer_id, 'countered')
            shark_id = offer.get('sharkId')

            # Generate shark response to counter
            threading.Thread(
                target=handle_counter_offer,
                args=(session_id, shark_id, offer, counter_terms),
                daemon=True
            ).start()

            return jsonify({'result': 'counter_submitted'})

    return jsonify({'error': 'Invalid action'}), 400


def handle_offer_decline(session_id, shark_id, original_offer):
    """Handle when user declines an offer."""
    session = session_manager.get_session(session_id)
    if not session:
        return

    state = session_manager.get_shark_state(session_id, shark_id)
    confidence = state.get('confidence', 50)

    # Reduce confidence
    new_confidence = max(0, confidence - 15)
    session_manager.update_shark_state(session_id, shark_id, {'confidence': new_confidence})

    # Check if shark goes out
    if new_confidence < 30:
        out_reason = shark_manager.get_out_reason(shark_id)
        session_manager.update_shark_state(session_id, shark_id, {'status': 'out'})
        send_sse_event(session_id, 'shark_out', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id),
            'message': out_reason
        })
    else:
        # Generate disappointed response
        response = ai_client.generate_decline_response(
            shark_id=shark_id,
            persona=shark_manager.get_persona(shark_id),
            original_offer=original_offer
        )
        if response:
            tts_result = tts_client.synthesize_for_shark(shark_id, response)
            send_sse_event(session_id, 'shark_message', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'text': response,
                'audio': tts_result if tts_result.get('audioData') else None,
                'duration': tts_result.get('duration', 0)
            })


def handle_counter_offer(session_id, shark_id, original_offer, counter_terms):
    """Handle when user makes a counter offer."""
    session = session_manager.get_session(session_id)
    if not session:
        return

    pitch_data = session.get('pitchData', {})

    # Thinking
    send_sse_event(session_id, 'shark_thinking', {
        'sharkId': shark_id,
        'sharkName': shark_manager.get_shark_name(shark_id)
    })

    # Generate response to counter
    response, accepts = ai_client.generate_counter_response(
        shark_id=shark_id,
        persona=shark_manager.get_persona(shark_id),
        original_offer=original_offer,
        counter_terms=counter_terms,
        pitch_data=pitch_data
    )

    send_sse_event(session_id, 'shark_speaking', {
        'sharkId': shark_id,
        'sharkName': shark_manager.get_shark_name(shark_id),
        'speaking': True
    })

    # Synthesize TTS for response
    tts_result = tts_client.synthesize_for_shark(shark_id, response)

    if accepts:
        # Shark accepts counter!
        final_offer = {
            **original_offer,
            'amount': counter_terms.get('amount', original_offer.get('amount')),
            'equity': counter_terms.get('equity', original_offer.get('equity')),
            'status': 'accepted'
        }
        session_manager.set_final_deal(session_id, final_offer)

        send_sse_event(session_id, 'shark_message', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id),
            'text': response,
            'audio': tts_result if tts_result.get('audioData') else None,
            'duration': tts_result.get('duration', 0)
        })

        send_sse_event(session_id, 'deal_closed', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id),
            'offer': final_offer
        })
    else:
        # Shark rejects counter or makes new offer
        send_sse_event(session_id, 'shark_message', {
            'sharkId': shark_id,
            'sharkName': shark_manager.get_shark_name(shark_id),
            'text': response,
            'audio': tts_result if tts_result.get('audioData') else None,
            'duration': tts_result.get('duration', 0)
        })

        # Check if there's a new offer in the response
        new_offer = shark_manager.parse_offer_from_response(shark_id, response, pitch_data)
        if new_offer:
            session_manager.add_offer(session_id, new_offer)
            send_sse_event(session_id, 'shark_offer', {
                'sharkId': shark_id,
                'sharkName': shark_manager.get_shark_name(shark_id),
                'offer': new_offer
            })

    send_sse_event(session_id, 'shark_speaking', {
        'sharkId': shark_id,
        'speaking': False
    })


# =============================================================================
# TTS Endpoint (for future Eleven Labs integration)
# =============================================================================

@app.route('/api/tts/synthesize', methods=['POST'])
def synthesize_speech():
    """Synthesize speech from text (placeholder for Eleven Labs)."""
    data = request.json
    text = data.get('text', '')
    voice_id = data.get('voiceId', 'default')

    result = tts_client.synthesize(text, voice_id)
    return jsonify(result)


# =============================================================================
# Speech-to-Text Endpoint (OpenAI Whisper)
# =============================================================================

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    """Transcribe audio using OpenAI Whisper API."""
    if not openai_client:
        return jsonify({
            'success': False,
            'error': 'OpenAI API key not configured',
            'text': ''
        }), 503

    if 'audio' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No audio file provided',
            'text': ''
        }), 400

    audio_file = request.files['audio']

    try:
        # Get file extension from filename
        filename = audio_file.filename or 'audio.webm'
        ext = os.path.splitext(filename)[1] or '.webm'
        print(f"[Whisper] Received file: {filename}, ext: {ext}")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        file_size = os.path.getsize(tmp_path)
        print(f"[Whisper] Saved temp file: {file_size} bytes")

        # Skip very small files (likely empty/noise)
        if file_size < 5000:
            os.unlink(tmp_path)
            return jsonify({
                'success': False,
                'error': 'Audio too short',
                'text': ''
            })

        # Convert to mp3 using ffmpeg (Whisper prefers mp3)
        mp3_path = tmp_path.replace(ext, '.mp3')
        try:
            # Use full path to ffmpeg
            ffmpeg_path = '/opt/homebrew/bin/ffmpeg'
            result = subprocess.run([
                ffmpeg_path, '-i', tmp_path,
                '-vn', '-acodec', 'libmp3lame', '-q:a', '4',
                '-y', mp3_path
            ], capture_output=True, timeout=30)

            if result.returncode == 0 and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                # Use converted mp3
                os.unlink(tmp_path)
                tmp_path = mp3_path
                print(f"[Whisper] Converted to mp3: {os.path.getsize(mp3_path)} bytes")
            else:
                # ffmpeg failed - try converting to wav instead
                wav_path = tmp_path.replace(ext, '.wav')
                result2 = subprocess.run([
                    ffmpeg_path, '-i', tmp_path,
                    '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                    '-y', wav_path
                ], capture_output=True, timeout=30)

                if result2.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                    os.unlink(tmp_path)
                    tmp_path = wav_path
                    print(f"[Whisper] Converted to wav: {os.path.getsize(wav_path)} bytes")
                else:
                    print(f"[Whisper] ffmpeg failed for both mp3 and wav: {result.stderr.decode()[:200]}")
        except FileNotFoundError:
            print("[Whisper] ffmpeg not found, using original format")
        except Exception as e:
            print(f"[Whisper] Conversion error: {e}")

        # Transcribe with Whisper
        with open(tmp_path, 'rb') as f:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en"
            )

        # Clean up temp files
        os.unlink(tmp_path)
        if os.path.exists(mp3_path) and mp3_path != tmp_path:
            os.unlink(mp3_path)

        print(f"[Whisper] Transcribed: {transcript.text[:50]}...")

        return jsonify({
            'success': True,
            'text': transcript.text
        })

    except Exception as e:
        print(f"[Whisper] Error: {e}")
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except:
            pass

        return jsonify({
            'success': False,
            'error': str(e),
            'text': ''
        }), 500


@app.route('/api/transcribe/status', methods=['GET'])
def transcribe_status():
    """Check if Whisper transcription is available."""
    return jsonify({
        'available': openai_client is not None,
        'message': 'Whisper ready' if openai_client else 'OpenAI API key not configured'
    })


# =============================================================================
# Verification Endpoints
# =============================================================================

@app.route('/api/verify/defi/search', methods=['GET'])
def search_defi_protocols():
    """Search DefiLlama for protocols by name."""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({'error': 'Query too short', 'results': []}), 400

    results = search_protocols(query)
    return jsonify({'results': results})


@app.route('/api/verify/defi', methods=['POST'])
@require_auth
def verify_defi_protocol():
    """
    Verify user owns a DeFi protocol via Twitter match.
    Requires authentication.
    """
    data = request.json
    protocol_slug = data.get('protocolSlug')

    if not protocol_slug:
        return jsonify({'error': 'Protocol slug required'}), 400

    # Get user's Twitter handle
    twitter_handle = None
    if request.user_data:
        twitter_handle = request.user_data.get('twitterHandle')

    if not twitter_handle:
        return jsonify({
            'error': 'Twitter handle not found. Please sign in with Twitter.',
            'verified': False
        }), 400

    # Verify ownership
    result = verify_protocol_ownership(twitter_handle, protocol_slug)

    # If verified, save to user profile
    if result.get('verified'):
        from firebase_admin_init import update_user_verification
        try:
            update_user_verification(request.user['uid'], 'defi', {
                'protocol': result.get('protocol'),
                'metrics': result.get('metrics'),
                'verifiedAt': int(__import__('time').time() * 1000)
            })
        except Exception as e:
            print(f"[Verification] Failed to save verification: {e}")

    return jsonify(result)


@app.route('/api/verify/trustmrr', methods=['POST'])
@require_auth
def verify_trustmrr_profile():
    """
    Verify user owns a TrustMRR profile via Twitter match.
    Requires authentication.
    """
    data = request.json
    profile_url = data.get('profileUrl')

    if not profile_url:
        return jsonify({'error': 'TrustMRR profile URL required'}), 400

    # Get user's Twitter handle
    twitter_handle = None
    if request.user_data:
        twitter_handle = request.user_data.get('twitterHandle')

    if not twitter_handle:
        return jsonify({
            'error': 'Twitter handle not found. Please sign in with Twitter.',
            'verified': False
        }), 400

    # Verify ownership
    result = verify_mrr_ownership(twitter_handle, profile_url)

    # If verified, save to user profile
    if result.get('verified'):
        from firebase_admin_init import update_user_verification
        try:
            update_user_verification(request.user['uid'], 'trustmrr', {
                'profile': result.get('profile'),
                'metrics': result.get('metrics'),
                'verifiedAt': int(__import__('time').time() * 1000)
            })
        except Exception as e:
            print(f"[Verification] Failed to save verification: {e}")

    return jsonify(result)


@app.route('/api/verify/status', methods=['GET'])
@require_auth
def get_verification_status():
    """Get current user's verification status."""
    verifications = {}
    if request.user_data:
        verifications = request.user_data.get('verifications', {})

    return jsonify({
        'verified': bool(verifications),
        'verifications': verifications
    })


# =============================================================================
# Leaderboard Endpoints
# =============================================================================

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get leaderboard entries."""
    from firebase_admin_init import get_leaderboard_from_firestore

    verified_only = request.args.get('verified', 'true').lower() == 'true'
    limit_count = min(int(request.args.get('limit', 50)), 100)

    entries = get_leaderboard_from_firestore(verified_only=verified_only, limit_count=limit_count)
    return jsonify({'entries': entries})


@app.route('/api/leaderboard/user/<user_id>', methods=['GET'])
def get_user_leaderboard_entry(user_id):
    """Get a specific user's best pitch."""
    from firebase_admin_init import get_user_pitches

    pitches = get_user_pitches(user_id, limit_count=1)
    if pitches:
        return jsonify({'entry': pitches[0]})
    return jsonify({'entry': None})


# =============================================================================
# Rate Limit Status
# =============================================================================

@app.route('/api/rate-limit/status', methods=['GET'])
@optional_auth
def get_rate_limit_status():
    """Get current user's rate limit status."""
    user_id = None
    if hasattr(request, 'user') and request.user:
        user_id = request.user.get('uid')

    stats = rate_limiter.get_user_stats(user_id)
    return jsonify(stats)


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    import ssl

    # Railway sets PORT env var - use it for production
    port = int(os.environ.get('PORT', 8443))
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('PORT')

    if is_production:
        # Railway handles SSL termination, run on HTTP
        print(f"Starting Flask server on port {port} (Railway production mode)...")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    else:
        # Local development with optional HTTPS
        cert_path = os.path.join('..', 'cert.pem')
        key_path = os.path.join('..', 'key.pem')

        if os.path.exists(cert_path) and os.path.exists(key_path):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert_path, key_path)
            print(f"Starting Flask server with HTTPS on port {port}...")
            app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True, threaded=True)
        else:
            print(f"SSL certificates not found. Starting on HTTP port {port}...")
            print("Note: Speech recognition requires HTTPS.")
            app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
