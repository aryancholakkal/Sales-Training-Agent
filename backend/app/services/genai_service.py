import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
import google.generativeai as genai
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class GenAIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model: Optional[Any] = None
        self.chat_session: Optional[Any] = None
        self.status = AgentStatus.IDLE
        self._on_message_callback: Optional[Callable] = None
        self._on_status_callback: Optional[Callable] = None

    async def create_session(
        self,
        persona_instruction: str,
        on_message_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None
    ) -> bool:
        """Create a new GenAI session using standard API"""
        try:
            self.status = AgentStatus.CONNECTING
            if on_status_callback:
                await on_status_callback(self.status)

            # Create the model with system instruction
            self.model = genai.GenerativeModel(
                model_name='gemini-2.0-flash-exp',
                system_instruction=persona_instruction,
                generation_config=genai.GenerationConfig(
                    temperature=0.8,
                    top_p=0.95,
                    max_output_tokens=1024,
                    response_mime_type="text/plain",
                ),
            )

            # Start a chat session
            self.chat_session = self.model.start_chat(history=[])
            self._on_message_callback = on_message_callback
            self._on_status_callback = on_status_callback

            self.status = AgentStatus.LISTENING
            if on_status_callback:
                await on_status_callback(self.status)

            logger.info("GenAI session initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to create GenAI session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False

    async def send_audio(self, audio_data: str) -> bool:
        """Send audio data to GenAI session (not supported in standard API)"""
        logger.warning("Audio input not supported in current GenAI implementation")
        return False

    async def send_text(self, text: str) -> bool:
        """Send text message to GenAI session"""
        if not self.chat_session:
            return False

        try:
            self.status = AgentStatus.THINKING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            # Send text message and get response
            response = await self.chat_session.send_message_async(text)

            # Extract text from response
            response_text = ""
            if response.text:
                response_text = response.text.strip()

            if response_text and self._on_message_callback:
                await self._on_message_callback(response_text)

            self.status = AgentStatus.LISTENING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            logger.info(f"Sent text message and received response: {len(response_text)} chars")
            return True
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            self.status = AgentStatus.ERROR
            if self._on_status_callback:
                await self._on_status_callback(self.status)
            return False

    async def close_session(self):
        """Close the GenAI session"""
        try:
            # Clear the session
            self.chat_session = None
            self.model = None
            self.status = AgentStatus.IDLE
            logger.info("GenAI session closed")
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status