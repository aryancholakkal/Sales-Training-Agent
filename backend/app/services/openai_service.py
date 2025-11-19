import os
import asyncio
import logging
import base64
from typing import Optional, Callable, Dict, Any, List
from openai import AsyncOpenAI
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)

# Optionally load .env if python-dotenv is installed so OPENAI_TTS_RESPONSE_FORMAT can be defined there
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class OpenAITTSService:
    def __init__(self, api_key: str, voice: str = "alloy", model: str = "tts-1"):
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
        self.status = AgentStatus.IDLE
        self._on_audio_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._stop_stream_event: Optional[asyncio.Event] = None
        self._active_stream_response: Optional[Any] = None
        self._stream_active: bool = False
        # Default response format can be configured via environment variable OPENAI_TTS_RESPONSE_FORMAT
        # Acceptable values: 'mp3' or 'pcm' (or other formats supported by the API)
        self.default_response_format = os.getenv('OPENAI_TTS_RESPONSE_FORMAT', 'mp3')
        logger.info(f"OpenAITTSService configured default_response_format={self.default_response_format}")

    async def generate_speech_with_params(self, text: str) -> dict:
        """Generate MP3 speech and return audio parameters and base64 data."""
        try:
            response_format = self.default_response_format or 'mp3'
            response = await self.client.audio.speech.create(
                model="tts-1-hd",
                voice=self.voice,
                input=text,
                response_format=response_format,
                speed=1.0
            )
            audio_bytes = b""
            async for chunk in response.aiter_bytes():
                audio_bytes += chunk
            base64_encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
            if response_format == 'pcm':
                return {
                    "mime_type": "audio/pcm;rate=24000;encoding=signed-integer;bits=16",
                    "sample_rate": 24000,
                    "channels": 1,
                    "bit_depth": 16,
                    "codec": "pcm",
                    "data": base64_encoded_audio
                }
            # default to mp3-like metadata
            return {
                "mime_type": "audio/mpeg",
                "sample_rate": 24000,
                "channels": 1,
                "bit_rate": 192000,
                "codec": "mp3",
                "data": base64_encoded_audio
            }
            
        except Exception as e:
            logger.error(f"Failed to generate OpenAI TTS with params: {e}")
            return {
                "error": str(e)
            }
    """Service for handling Text-to-Speech using OpenAI's TTS API"""

    

    async def initialize_session(
        self,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        on_audio_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None
    ) -> bool:
        """Initialize TTS session"""
        try:
            self.status = AgentStatus.CONNECTING

            if voice:
                self.voice = voice

            if model:
                self.model = model

            self._on_audio_callback = on_audio_callback
            self._on_error_callback = on_error_callback

            # Test the connection by making a simple API call
            try:
                await self.client.models.list()
            except Exception as e:
                raise Exception(f"Failed to connect to OpenAI API: {e}")

            self.status = AgentStatus.LISTENING
            logger.info(f"OpenAI TTS session initialized with voice: {self.voice}, model: {self.model}")
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
        model: Optional[str] = None,
        response_format: Optional[str] = None
    ) -> Optional[bytes]:
        """Convert text to speech and return audio bytes"""
        if self.status == AgentStatus.ERROR:
            return None

        try:
            self.status = AgentStatus.SPEAKING

            # Use provided voice or default
            current_voice = voice or self.voice
            current_model = model or self.model

            # Determine response format (env override possible)
            response_format = response_format or self.default_response_format or 'mp3'
            # Generate speech
            response = await self.client.audio.speech.create(
                model=current_model,
                voice=current_voice,
                input=text,
                response_format=response_format
            )

            # Get audio bytes
            audio_bytes = b""
            async for chunk in response.aiter_bytes():
                audio_bytes += chunk

            # Trigger callback with audio data, include richer metadata for MP3
            if self._on_audio_callback:
                if response_format == "mp3":
                    mime_type = "audio/mpeg"
                    # Include recommended high-quality params
                    await self._on_audio_callback(
                        audio_bytes,
                        mime_type,
                        False,
                        bit_rate=192000,
                        codec="mp3",
                        sample_rate=24000,
                        channels=1
                    )
                elif response_format == "pcm":
                    mime_type = "audio/pcm;rate=24000;encoding=signed-integer;bits=16"
                    await self._on_audio_callback(
                        audio_bytes,
                        mime_type,
                        False,
                        bit_rate=None,
                        codec="pcm",
                        sample_rate=24000,
                        channels=1,
                        bit_depth=16,
                        encoding="signed-integer"
                    )
                else:
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
        model: Optional[str] = None,
        response_format: Optional[str] = None
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
        model: Optional[str] = None,
        response_format: Optional[str] = None
    ) -> None:
        """Stream text to speech with real-time audio chunks"""
        if self.status == AgentStatus.ERROR:
            return

        stop_event = asyncio.Event()
        self._stop_stream_event = stop_event
        self._stream_active = True
        stopped_early = False

        try:
            self.status = AgentStatus.SPEAKING

            # Use provided voice or default
            current_voice = voice or self.voice
            current_model = model or self.model

            # Determine response format (env override possible)
            response_format = response_format or self.default_response_format or 'mp3'

            # Stream audio generation using OpenAI's streaming response
            async with self.client.audio.speech.with_streaming_response.create(
                model=current_model,
                voice=current_voice,
                input=text,
                response_format=response_format
            ) as response:
                self._active_stream_response = response
                # Stream audio chunks with small delay for better real-time experience
                async for chunk in response.iter_bytes(chunk_size=1024):
                    if stop_event.is_set():
                        logger.info("OpenAI TTS stream stop requested; ending stream early")
                        stopped_early = True
                        break

                    if chunk and self._on_audio_callback:
                        if response_format == "mp3":
                            mime_type = "audio/mpeg"
                            await self._on_audio_callback(
                                chunk,
                                mime_type,
                                True,
                                bit_rate=192000,
                                codec="mp3",
                                sample_rate=24000,
                                channels=1
                            )
                        elif response_format == "pcm":
                            # PCM streaming: send raw PCM chunks with metadata
                            mime_type = "audio/pcm;rate=24000;encoding=signed-integer;bits=16"
                            await self._on_audio_callback(
                                chunk,
                                mime_type,
                                True,
                                bit_rate=None,
                                codec="pcm",
                                sample_rate=24000,
                                channels=1,
                                bit_depth=16,
                                encoding="signed-integer"
                            )
                        else:
                            mime_type = f"audio/{response_format}"
                            await self._on_audio_callback(chunk, mime_type, is_stream=True)
                    # Small delay to prevent overwhelming the audio playback
                    await asyncio.sleep(0.01)

            if not stopped_early:
                logger.info(f"Completed streaming OpenAI TTS for text: {text[:50]}...")

            self.status = AgentStatus.LISTENING
        except asyncio.CancelledError:
            logger.info("OpenAI TTS streaming coroutine cancelled")
            self.status = AgentStatus.LISTENING
            raise
        except Exception as e:
            logger.error(f"Failed to stream OpenAI TTS: {e}")
            self.status = AgentStatus.ERROR
            if self._on_error_callback:
                await self._on_error_callback(f"OpenAI TTS streaming failed: {str(e)}")
        finally:
            self._stream_active = False
            self._stop_stream_event = None
            self._active_stream_response = None
            # Ensure status is reset if stream ended with an error and callback not triggered
            if self.status != AgentStatus.ERROR:
                self.status = AgentStatus.LISTENING

    async def stop_stream(self, reason: Optional[str] = None) -> bool:
        """Request the active streaming session to stop."""
        stop_event = self._stop_stream_event
        if not stop_event:
            return False

        if not stop_event.is_set():
            stop_event.set()
            logger.info(f"OpenAI TTS stop requested{f' ({reason})' if reason else ''}")

        response = self._active_stream_response
        if response and hasattr(response, "aclose"):
            try:
                await response.aclose()
            except Exception as e:
                logger.debug(f"OpenAI TTS response close error: {e}")

        self._stream_active = False
        return True

    def is_streaming(self) -> bool:
        """Return True when a streaming TTS session is active."""
        return self._stream_active

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

    def get_current_model(self) -> str:
        """Get the current model"""
        return self.model