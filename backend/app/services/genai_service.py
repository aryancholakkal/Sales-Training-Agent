import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from google.generativeai import configure, GenerativeModel
from google.generativeai.types import LiveSession, LiveServerMessage, Modality
import google.generativeai as genai
from ..models.session import AgentStatus
from ..services.audio_service import AudioService

logger = logging.getLogger(__name__)


class GenAIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        configure(api_key=api_key)
        self.session: Optional[LiveSession] = None
        self.status = AgentStatus.IDLE
        
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
            
            # Create the live session
            model = GenerativeModel('gemini-2.0-flash-exp')
            
            config = {
                'response_modalities': [Modality.AUDIO],
                'speech_config': {
                    'voice_config': {'prebuilt_voice_config': {'voice_name': 'Zephyr'}}
                },
                'system_instruction': persona_instruction,
                'input_audio_transcription': {},
                'output_audio_transcription': {}
            }
            
            # Set up callbacks
            callbacks = {
                'onopen': self._on_session_open,
                'onmessage': lambda msg: self._on_message(msg, on_message_callback),
                'onerror': self._on_error,
                'onclose': self._on_close
            }
            
            self.session = await model.live.connect(config=config, callbacks=callbacks)
            return True
            
        except Exception as e:
            logger.error(f"Failed to create GenAI session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False
    
    async def send_audio(self, audio_data: str) -> bool:
        """Send audio data to GenAI session"""
        if not self.session:
            return False
            
        try:
            blob = AudioService.create_audio_blob(audio_data)
            await self.session.send_realtime_input({'media': blob})
            return True
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            return False
    
    async def close_session(self):
        """Close the GenAI session"""
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self.session = None
                self.status = AgentStatus.IDLE
    
    def _on_session_open(self):
        """Handle session open event"""
        self.status = AgentStatus.LISTENING
        logger.info("GenAI session opened")
    
    async def _on_message(self, message: LiveServerMessage, callback: Optional[Callable]):
        """Handle incoming messages from GenAI"""
        try:
            if callback:
                await callback(message)
                
            # Update status based on message content
            if hasattr(message, 'server_content'):
                if message.server_content.get('model_turn'):
                    self.status = AgentStatus.SPEAKING
                elif message.server_content.get('turn_complete'):
                    self.status = AgentStatus.LISTENING
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def _on_error(self, error):
        """Handle session errors"""
        logger.error(f"GenAI session error: {error}")
        self.status = AgentStatus.ERROR
    
    def _on_close(self, event):
        """Handle session close"""
        logger.info("GenAI session closed")
        self.status = AgentStatus.IDLE
        self.session = None
    
    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status