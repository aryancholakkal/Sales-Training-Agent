import os
import asyncio
import logging
import base64
from typing import Optional, Callable, Dict, Any, List
from elevenlabs import VoiceSettings, Voice
from elevenlabs.client import AsyncElevenLabs
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """Service for handling Text-to-Speech using ElevenLabs"""
    
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.client = AsyncElevenLabs(api_key=api_key)
        self.status = AgentStatus.IDLE
        self._on_audio_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._voice_settings = VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0,
            use_speaker_boost=True
        )

    async def initialize_session(
        self,
        voice_id: Optional[str] = None,
        on_audio_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None
    ) -> bool:
        """Initialize TTS session"""
        try:
            self.status = AgentStatus.CONNECTING
            
            if voice_id:
                self.voice_id = voice_id
            
            self._on_audio_callback = on_audio_callback
            self._on_error_callback = on_error_callback

            # Test the connection by getting available voices
            available_voices = await self.get_available_voices()
            if not available_voices:
                raise Exception("Failed to connect to ElevenLabs API")

            # Verify the selected voice exists
            voice_exists = any(voice.voice_id == self.voice_id for voice in available_voices)
            if not voice_exists:
                logger.warning(f"Voice ID {self.voice_id} not found, using default")
                self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default Rachel voice

            self.status = AgentStatus.LISTENING
            logger.info(f"ElevenLabs TTS session initialized with voice: {self.voice_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs session: {e}")
            self.status = AgentStatus.ERROR
            if on_error_callback:
                await on_error_callback(f"ElevenLabs initialization failed: {str(e)}")
            return False

    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_monolingual_v1",
        voice_settings: Optional[VoiceSettings] = None
    ) -> Optional[bytes]:
        """Convert text to speech and return audio bytes"""
        if self.status == AgentStatus.ERROR:
            return None

        try:
            self.status = AgentStatus.SPEAKING
            
            # Use provided voice_id or default
            current_voice_id = voice_id or self.voice_id
            current_voice_settings = voice_settings or self._voice_settings

            # Generate speech
            audio_generator = await self.client.generate(
                text=text,
                voice=Voice(voice_id=current_voice_id),
                voice_settings=current_voice_settings,
                model=model
            )

            # Collect audio bytes
            audio_bytes = b""
            async for chunk in audio_generator:
                audio_bytes += chunk

            # Trigger callback with audio data
            if self._on_audio_callback:
                await self._on_audio_callback(audio_bytes, "audio/mpeg")

            self.status = AgentStatus.LISTENING
            logger.info(f"Generated TTS audio: {len(audio_bytes)} bytes for text: {text[:50]}...")
            return audio_bytes

        except Exception as e:
            logger.error(f"Failed to generate TTS: {e}")
            self.status = AgentStatus.ERROR
            if self._on_error_callback:
                await self._on_error_callback(f"TTS generation failed: {str(e)}")
            return None

    async def text_to_speech_base64(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_monolingual_v1",
        voice_settings: Optional[VoiceSettings] = None
    ) -> Optional[str]:
        """Convert text to speech and return base64 encoded audio"""
        audio_bytes = await self.text_to_speech(text, voice_id, model, voice_settings)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode('utf-8')
        return None

    async def stream_text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_monolingual_v1",
        voice_settings: Optional[VoiceSettings] = None
    ) -> None:
        """Stream text to speech with real-time audio chunks"""
        if self.status == AgentStatus.ERROR:
            return

        try:
            self.status = AgentStatus.SPEAKING
            
            # Use provided voice_id or default
            current_voice_id = voice_id or self.voice_id
            current_voice_settings = voice_settings or self._voice_settings

            # Stream audio generation
            audio_generator = await self.client.generate(
                text=text,
                voice=Voice(voice_id=current_voice_id),
                voice_settings=current_voice_settings,
                model=model,
                stream=True
            )

            # Stream audio chunks
            async for chunk in audio_generator:
                if self._on_audio_callback:
                    await self._on_audio_callback(chunk, "audio/mpeg", is_stream=True)

            self.status = AgentStatus.LISTENING
            logger.info(f"Completed streaming TTS for text: {text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to stream TTS: {e}")
            self.status = AgentStatus.ERROR
            if self._on_error_callback:
                await self._on_error_callback(f"TTS streaming failed: {str(e)}")

    async def get_available_voices(self) -> List[Voice]:
        """Get list of available voices"""
        try:
            voices_response = await self.client.voices.get_all()
            return voices_response.voices
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []

    async def clone_voice(
        self,
        name: str,
        files: List[str],
        description: Optional[str] = None
    ) -> Optional[str]:
        """Clone a voice from audio files (returns voice_id if successful)"""
        try:
            # Read audio files
            file_data = []
            for file_path in files:
                with open(file_path, 'rb') as f:
                    file_data.append(f.read())

            # Clone voice
            voice = await self.client.clone(
                name=name,
                files=file_data,
                description=description or f"Cloned voice: {name}"
            )

            logger.info(f"Voice cloned successfully: {voice.voice_id}")
            return voice.voice_id

        except Exception as e:
            logger.error(f"Failed to clone voice: {e}")
            return None

    async def get_voice_info(self, voice_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get information about a specific voice"""
        try:
            current_voice_id = voice_id or self.voice_id
            voice = await self.client.voices.get(current_voice_id)
            
            return {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category,
                "description": voice.description,
                "settings": {
                    "stability": voice.settings.stability if voice.settings else None,
                    "similarity_boost": voice.settings.similarity_boost if voice.settings else None,
                    "style": voice.settings.style if voice.settings else None,
                    "use_speaker_boost": voice.settings.use_speaker_boost if voice.settings else None,
                }
            }
        except Exception as e:
            logger.error(f"Failed to get voice info: {e}")
            return None

    def set_voice_settings(
        self,
        stability: float = 0.71,
        similarity_boost: float = 0.5,
        style: float = 0.0,
        use_speaker_boost: bool = True
    ):
        """Update voice settings"""
        self._voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost
        )
        logger.info("Voice settings updated")

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice"""
        try:
            await self.client.voices.delete(voice_id)
            logger.info(f"Voice {voice_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete voice {voice_id}: {e}")
            return False

    async def close_session(self):
        """Close the TTS session"""
        try:
            # Cleanup any resources if needed
            self.status = AgentStatus.IDLE
            logger.info("ElevenLabs TTS session closed")
        except Exception as e:
            logger.error(f"Error closing ElevenLabs session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def get_current_voice_id(self) -> str:
        """Get the current voice ID"""
        return self.voice_id

    def set_voice_id(self, voice_id: str):
        """Set the voice ID for TTS"""
        self.voice_id = voice_id
        logger.info(f"Voice ID updated to: {voice_id}")