import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
import google.generativeai as genai
from ..models.session import AgentStatus
from ..services.audio_service import AudioService

logger = logging.getLogger(__name__)


class GenAIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.session: Optional[Any] = None
        self.status = AgentStatus.IDLE
        self._message_task: Optional[asyncio.Task] = None
        self._on_message_callback: Optional[Callable] = None
        self._on_status_callback: Optional[Callable] = None

    async def create_session(
        self,
        persona_instruction: str,
        on_message_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None
    ) -> bool:
        """Create a new GenAI live session"""
        try:
            self.status = AgentStatus.CONNECTING
            if on_status_callback:
                await on_status_callback(self.status)

            # Configure the live session
            config = genai.live.LiveConnectConfig(
                response_modalities=["text"],
                speech_config=genai.live.SpeechConfig(
                    voice_config=genai.live.VoiceConfig(
                        prebuilt_voice_config=genai.live.PrebuiltVoiceConfig(
                            voice_name="Puck"
                        )
                    )
                ),
                system_instruction=persona_instruction,
                generation_config=genai.live.GenerationConfig(
                    temperature=0.8,
                    top_p=0.95,
                    max_output_tokens=1024,
                    response_mime_type="text/plain",
                ),
            )

            # Connect to live session
            self.session = genai.live.connect(model='gemini-2.0-flash-exp', config=config)
            self._on_message_callback = on_message_callback
            self._on_status_callback = on_status_callback

            # Start listening for messages
            self._message_task = asyncio.create_task(self._listen_for_messages())

            self.status = AgentStatus.LISTENING
            if on_status_callback:
                await on_status_callback(self.status)

            logger.info("GenAI live session initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to create GenAI session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False

    async def _listen_for_messages(self):
        """Listen for incoming messages from the live session"""
        try:
            async for message in self.session:
                if message.text and self._on_message_callback:
                    await self._on_message_callback(message.text)
                elif message.status and self._on_status_callback:
                    # Map status if needed
                    await self._on_status_callback(self.status)
        except Exception as e:
            logger.error(f"Error listening for messages: {e}")
            self.status = AgentStatus.ERROR
            if self._on_status_callback:
                await self._on_status_callback(self.status)

    async def send_audio(self, audio_data: str) -> bool:
        """Send audio data to GenAI live session"""
        if not self.session:
            return False

        try:
            # Decode base64 audio data to bytes
            audio_bytes = AudioService.decode(audio_data)

            # Create audio blob
            audio_blob = AudioService.create_audio_blob(audio_bytes, 'audio/pcm;rate=16000')

            # Send audio message
            await self.session.send(audio_blob)

            logger.info(f"Sent audio data of length: {len(audio_bytes)} bytes")
            return True
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            return False

    async def send_text(self, text: str) -> bool:
        """Send text message to GenAI live session"""
        if not self.session:
            return False

        try:
            self.status = AgentStatus.SPEAKING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            # Send text message
            await self.session.send(text)

            self.status = AgentStatus.LISTENING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            logger.info(f"Sent text message: {text}")
            return True
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            self.status = AgentStatus.ERROR
            if self._on_status_callback:
                await self._on_status_callback(self.status)
            return False

    async def close_session(self):
        """Close the GenAI live session"""
        if self.session:
            try:
                await self.session.close()
                logger.info("GenAI live session closed")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self.session = None
                self.status = AgentStatus.IDLE
                if self._message_task:
                    self._message_task.cancel()
                    try:
                        await self._message_task
                    except asyncio.CancelledError:
                        pass
                    self._message_task = None

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status