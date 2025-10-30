import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any, List
from groq import AsyncGroq
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class GroqService:
    """Service for handling LLM interactions using Groq API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = AsyncGroq(api_key=api_key)
        self.status = AgentStatus.IDLE
        self._conversation_history: List[Dict[str, str]] = []
        self._on_message_callback: Optional[Callable] = None
        self._on_status_callback: Optional[Callable] = None
        self._system_prompt: str = ""

    async def initialize_session(
        self,
        persona_instruction: str,
        on_message_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None
    ) -> bool:
        """Initialize a new Groq LLM session"""
        try:
            self.status = AgentStatus.CONNECTING
            if on_status_callback:
                await on_status_callback(self.status)

            # Store callbacks and system prompt
            self._on_message_callback = on_message_callback
            self._on_status_callback = on_status_callback
            self._system_prompt = persona_instruction
            
            # Clear conversation history
            self._conversation_history = [
                {"role": "system", "content": persona_instruction}
            ]

            # Test the connection with a simple call
            test_response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
                temperature=0.1
            )

            self.status = AgentStatus.LISTENING
            if on_status_callback:
                await on_status_callback(self.status)

            logger.info("Groq LLM session initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Groq session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False

    async def send_message(self, message: str, user_role: str = "user") -> Optional[str]:
        """Send a message to Groq and get response"""
        if self.status == AgentStatus.ERROR:
            return None

        try:
            self.status = AgentStatus.SPEAKING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            # Add user message to conversation history
            self._conversation_history.append({
                "role": user_role,
                "content": message
            })

            # Get response from Groq
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self._conversation_history,
                max_tokens=1024,
                temperature=0.8,
                top_p=0.95,
                stream=False
            )

            assistant_message = response.choices[0].message.content
            
            # Add assistant response to conversation history
            self._conversation_history.append({
                "role": "assistant", 
                "content": assistant_message
            })

            # Trigger callback with the response
            if self._on_message_callback:
                await self._on_message_callback(assistant_message)

            self.status = AgentStatus.LISTENING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            logger.info(f"Groq response generated: {len(assistant_message)} characters")
            return assistant_message

        except Exception as e:
            logger.error(f"Failed to get Groq response: {e}")
            self.status = AgentStatus.ERROR
            if self._on_status_callback:
                await self._on_status_callback(self.status)
            return None

    async def stream_message(self, message: str, user_role: str = "user") -> None:
        """Send a message to Groq and stream the response"""
        if self.status == AgentStatus.ERROR:
            return

        try:
            self.status = AgentStatus.SPEAKING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            # Add user message to conversation history
            self._conversation_history.append({
                "role": user_role,
                "content": message
            })

            # Get streaming response from Groq
            stream = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self._conversation_history,
                max_tokens=1024,
                temperature=0.8,
                top_p=0.95,
                stream=True
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    # Send partial response via callback
                    if self._on_message_callback:
                        await self._on_message_callback(content, is_partial=True)

            # Add complete response to conversation history
            if full_response:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })

                # Send final complete response
                if self._on_message_callback:
                    await self._on_message_callback(full_response, is_partial=False)

            self.status = AgentStatus.LISTENING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

            logger.info(f"Groq streaming response completed: {len(full_response)} characters")

        except Exception as e:
            logger.error(f"Failed to stream Groq response: {e}")
            self.status = AgentStatus.ERROR
            if self._on_status_callback:
                await self._on_status_callback(self.status)

    async def reset_conversation(self):
        """Reset the conversation history"""
        self._conversation_history = [
            {"role": "system", "content": self._system_prompt}
        ]
        logger.info("Conversation history reset")

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the current conversation history"""
        return self._conversation_history.copy()

    async def close_session(self):
        """Close the Groq session"""
        try:
            # Cleanup any resources if needed
            self._conversation_history.clear()
            self.status = AgentStatus.IDLE
            logger.info("Groq session closed")
        except Exception as e:
            logger.error(f"Error closing Groq session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status