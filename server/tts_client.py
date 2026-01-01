"""
Text-to-Speech Client for Shark Tank Simulator
Eleven Labs integration for shark voices
"""

import requests
import base64


# Voice ID mappings for each shark
# Custom Eleven Labs voices for each shark personality
SHARK_VOICES = {
    'marcus': {
        'voiceId': '0j3d9hmWUPu58jCTkS2a',  # Custom Marc voice
        'name': 'Marcus Kellan',
        'description': 'Deep, confident male voice (Mark Cuban style)'
    },
    'victor': {
        'voiceId': 'rWGG0VXK5AV5uUCVhkzq',  # Custom Kevin voice
        'name': 'Victor Slate',
        'description': 'Cold, calculating male voice (Kevin O\'Leary style)'
    },
    'elena': {
        'voiceId': 'jHxfbXCsWA2s73SylbEE',  # Custom Elena voice
        'name': 'Elena Brooks',
        'description': 'Warm, enthusiastic female voice (Lori Greiner style)'
    },
    'richard': {
        'voiceId': 'dhM7j5QUr0mRBkfdrTSq',  # Custom Richard voice
        'name': 'Richard Hale',
        'description': 'Warm, storytelling male voice (Richard Branson style)'
    },
    'daniel': {
        'voiceId': 'xGWtbEed7UIlZxIkSrUI',  # Custom Daniel voice
        'name': 'Daniel Frost',
        'description': 'Friendly, encouraging male voice (Robert Herjavec style)'
    }
}


class TTSClient:
    """Text-to-Speech client with Eleven Labs integration."""

    def __init__(self, api_key=None, base_url="https://api.elevenlabs.io/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.enabled = bool(api_key)

    def get_voice_id(self, shark_id):
        """Get the voice ID for a shark."""
        voice_config = SHARK_VOICES.get(shark_id, {})
        return voice_config.get('voiceId', 'pNInz6obpgDQGcFmaJgB')  # Default to Adam

    def estimate_duration(self, text):
        """Estimate speech duration in milliseconds (150 words per minute average)."""
        words = len(text.split())
        minutes = words / 150
        return int(minutes * 60 * 1000)

    def synthesize(self, text, voice_id):
        """
        Synthesize speech from text using Eleven Labs API.
        Returns base64-encoded audio data.
        """
        if not self.enabled:
            print(f"[TTS] Disabled - no API key. Key value: {self.api_key}")
            return {
                'enabled': False,
                'audioData': None,
                'duration': self.estimate_duration(text),
                'message': 'TTS disabled - no API key configured'
            }

        print(f"[TTS] Synthesizing for voice {voice_id}: {text[:50]}...")

        if not text or len(text.strip()) == 0:
            return {
                'enabled': True,
                'audioData': None,
                'duration': 0,
                'message': 'No text to synthesize'
            }

        try:
            headers = {
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': self.api_key
            }

            data = {
                'text': text,
                'model_id': 'eleven_turbo_v2_5',  # Updated model for free tier
                'voice_settings': {
                    'stability': 0.5,
                    'similarity_boost': 0.75
                }
            }

            response = requests.post(
                f'{self.base_url}/text-to-speech/{voice_id}',
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                # Convert audio to base64 for easy transport
                audio_base64 = base64.b64encode(response.content).decode('utf-8')
                print(f"[TTS] Success! Audio size: {len(response.content)} bytes")
                return {
                    'enabled': True,
                    'audioData': audio_base64,
                    'duration': self.estimate_duration(text),
                    'format': 'audio/mpeg'
                }
            else:
                print(f"[TTS] Eleven Labs API error: {response.status_code} - {response.text}")
                return {
                    'enabled': True,
                    'audioData': None,
                    'duration': self.estimate_duration(text),
                    'error': f'API error: {response.status_code}'
                }

        except requests.exceptions.Timeout:
            print("Eleven Labs API timeout")
            return {
                'enabled': True,
                'audioData': None,
                'duration': self.estimate_duration(text),
                'error': 'API timeout'
            }
        except Exception as e:
            print(f"Eleven Labs error: {e}")
            return {
                'enabled': True,
                'audioData': None,
                'duration': self.estimate_duration(text),
                'error': str(e)
            }

    def synthesize_for_shark(self, shark_id, text):
        """Convenience method to synthesize speech for a specific shark."""
        voice_id = self.get_voice_id(shark_id)
        return self.synthesize(text, voice_id)

    def get_available_voices(self):
        """Get list of available voices from Eleven Labs."""
        if not self.enabled:
            return {'voices': [], 'message': 'TTS disabled'}

        try:
            headers = {'xi-api-key': self.api_key}
            response = requests.get(f'{self.base_url}/voices', headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                return {'voices': [], 'error': f'API error: {response.status_code}'}
        except Exception as e:
            return {'voices': [], 'error': str(e)}

    def configure_voice(self, shark_id, voice_id):
        """Update the voice ID for a shark."""
        if shark_id in SHARK_VOICES:
            SHARK_VOICES[shark_id]['voiceId'] = voice_id
            return True
        return False
