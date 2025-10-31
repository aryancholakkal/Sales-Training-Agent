import os
import asyncio
import logging
import base64
from typing import Optional, Callable, Dict, Any, List
from openai import AsyncOpenAI
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class OpenAITTSService:
    """Service for handling Text-to-Speech using OpenAI's TTS API"""

    def __init__(self, api_key: str, voice: str = "alloy"):
        self.api_key = api_key
        self.voice = voice
        self.client = AsyncOpenAI(api_key=api_key)
        self.status = AgentStatus.IDLE
        self._on_audio_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None

    async def initialize_session(
        self,
        voice: Optional[str] = None,
        on_audio_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None
    ) -> bool:
        """Initialize TTS session"""
        try:
            self.status = AgentStatus.CONNECTING

            if voice:
                self.voice = voice

            self._on_audio_callback = on_audio_callback
            self._on_error_callback = on_error_callback

            # Test the connection by making a simple API call
            try:
                await self.client.models.list()
            except Exception as e:
                raise Exception(f"Failed to connect to OpenAI API: {e}")

            self.status = AgentStatus.LISTENING
            logger.info(f"OpenAI TTS session initialized with voice: {self.voice}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI TTS session: {e}")
            self.status = AgentStatus.ERROR
            if on_error_callback:
                await on_error_callback(f"OpenAI TTS initialization failed: {str(e)}")
            return False

    async def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: str = "tts-1",
        response_format: str = "mp3"
    ) -> Optional[bytes]:
        """Convert text to speech and return audio bytes"""
        if self.status == AgentStatus.ERROR:
            return None

        try:
            self.status = AgentStatus.SPEAKING

            # Use provided voice or default
            current_voice = voice or self.voice

            # Generate speech
            response = await self.client.audio.speech.create(
                model=model,
                voice=current_voice,
                input=text,
                response_format=response_format
            )

            # Get audio bytes
            audio_bytes = b""
            async for chunk in response.aiter_bytes():
                audio_bytes += chunk

            # Trigger callback with audio data
            if self._on_audio_callback:
                mime_type = f"audio/{response_format}"
                await self._on_audio_callback(audio_bytes, mime_type)

            self.status = AgentStatus.LISTENING
            logger.info(f"Generated OpenAI TTS audio: {len(audio_bytes)} bytes for text: {text[:50]}...")
            return audio_bytes

        except Exception as e:
            logger.error(f"Failed to generate OpenAI TTS: {e}")
            self.status = AgentStatus.ERROR
            if self._on_error_callback:
                await self._on_error_callback(f"OpenAI TTS generation failed: {str(e)}")
            return None

    async def text_to_speech_base64(
        self,
        text: str,
        voice: Optional[str] = None,
        model: str = "tts-1",
        response_format: str = "mp3"
    ) -> Optional[str]:
        """Convert text to speech and return base64 encoded audio"""
        audio_bytes = await self.text_to_speech(text, voice, model, response_format)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode('utf-8')
        return None

    async def stream_text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: str = "tts-1",
        response_format: str = "mp3"
    ) -> None:
        """Stream text to speech with real-time audio chunks"""
        if self.status == AgentStatus.ERROR:
            return

        try:
            self.status = AgentStatus.SPEAKING

            # Use provided voice or default
            current_voice = voice or self.voice

            # Stream audio generation
            response = await self.client.audio.speech.create(
                model=model,
                voice=current_voice,
                input=text,
                response_format=response_format
            )

            # Stream audio chunks
            async for chunk in response.aiter_bytes():
                if self._on_audio_callback:
                    mime_type = f"audio/{response_format}"
                    await self._on_audio_callback(chunk, mime_type, is_stream=True)

            self.status = AgentStatus.LISTENING
            logger.info(f"Completed streaming OpenAI TTS for text: {text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to stream OpenAI TTS: {e}")
            self.status = AgentStatus.ERROR
            if self._on_error_callback:
                await self._on_error_callback(f"OpenAI TTS streaming failed: {str(e)}")

    async def get_available_voices(self) -> List[str]:
        """Get list of available voices"""
        # OpenAI TTS supports these voices: alloy, echo, fable, onyx, nova, shimmer
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    async def get_voice_info(self, voice: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get information about a specific voice"""
        try:
            current_voice = voice or self.voice
            available_voices = await self.get_available_voices()

            if current_voice not in available_voices:
                return None

            return {
                "voice": current_voice,
                "description": f"OpenAI TTS voice: {current_voice}",
                "available": True
            }
        except Exception as e:
            logger.error(f"Failed to get voice info: {e}")
            return None

    def set_voice(self, voice: str):
        """Set the voice for TTS"""
        available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice in available_voices:
            self.voice = voice
            logger.info(f"Voice updated to: {voice}")
        else:
            logger.warning(f"Voice {voice} not available. Available voices: {available_voices}")

    async def close_session(self):
        """Close the TTS session"""
        try:
            # Cleanup any resources if needed
            self.status = AgentStatus.IDLE
            logger.info("OpenAI TTS session closed")
        except Exception as e:
            logger.error(f"Error closing OpenAI TTS session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def get_current_voice(self) -> str:
        """Get the current voice"""
        return self.voice