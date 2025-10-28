import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from google.generativeai import configure, GenerativeModel
import google.generativeai as genai
from ..models.session import AgentStatus
from ..services.audio_service import AudioService

logger = logging.getLogger(__name__)


class GenAIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        configure(api_key=api_key)
        self.session: Optional[Any] = None
        self.model: Optional[GenerativeModel] = None
        self.status = AgentStatus.IDLE
        
    async def create_session(
        self,
        persona_instruction: str,
        on_message_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None
    ) -> bool:
        """Create a new GenAI session (simplified version)"""
        try:
            self.status = AgentStatus.CONNECTING
            if on_status_callback:
                await on_status_callback(self.status)
            
            # Create a simple model instance for now
            self.model = GenerativeModel('gemini-1.5-flash')
            self.status = AgentStatus.LISTENING
            
            if on_status_callback:
                await on_status_callback(self.status)
            
            logger.info("GenAI service initialized (simplified mode)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create GenAI session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False
    
    async def send_audio(self, audio_data: str) -> bool:
        """Send audio data to GenAI session (mock implementation)"""
        if not self.model:
            return False
            
        try:
            # For now, just log that we received audio data
            logger.info(f"Received audio data of length: {len(audio_data)}")
            
            # Mock processing delay
            await asyncio.sleep(0.1)
            
            # Update status to speaking temporarily
            old_status = self.status
            self.status = AgentStatus.SPEAKING
            await asyncio.sleep(1)  # Simulate response time
            self.status = old_status
            
            return True
        except Exception as e:
            logger.error(f"Failed to process audio: {e}")
            return False
    
    async def send_text(self, text: str) -> str:
        """Send text to GenAI and get response"""
        if not self.model:
            return "GenAI service not initialized"
            
        try:
            self.status = AgentStatus.SPEAKING
            response = await self.model.generate_content_async(text)
            self.status = AgentStatus.LISTENING
            return response.text
        except Exception as e:
            logger.error(f"Failed to generate text response: {e}")
            self.status = AgentStatus.ERROR
            return f"Error: {str(e)}"
    
    async def close_session(self):
        """Close the GenAI session"""
        if self.model:
            try:
                # No explicit close needed for basic model
                self.model = None
                logger.info("GenAI session closed")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self.session = None
                self.status = AgentStatus.IDLE
    
    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status