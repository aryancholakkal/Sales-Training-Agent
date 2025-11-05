import asyncio
import websockets
import json
import base64
import logging
from typing import Optional, Callable
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class AssemblyAIService:
    """AssemblyAI Speech-to-Text service using updated Streaming API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running = False
        self.status = AgentStatus.IDLE
        self.on_transcript_callback: Optional[Callable] = None
        self.session_id: Optional[str] = None

        # Updated WebSocket URL for new streaming API
        # Using the new Streaming Speech-to-Text endpoint
        # Note: Token can be passed in URL or Authorization header
        # Current implementation uses both for compatibility
        self.ws_url = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

        # Background tasks
        self._receive_task: Optional[asyncio.Task] = None

    def get_status(self) -> AgentStatus:
        """Get current service status"""
        return self.status

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.ws is not None and self.ws.open and self.is_running

    async def initialize_session(self, on_transcript_callback: Optional[Callable] = None) -> bool:
        """
        Initialize AssemblyAI streaming session

        Args:
            on_transcript_callback: Callback for transcript updates

        Returns:
            bool: True if initialization successful
        """
        try:
            self.on_transcript_callback = on_transcript_callback

            logger.info(f"[STT] Connecting to AssemblyAI: {self.ws_url}")
            logger.info(f"[STT] Using API key: {self.api_key[:10]}...")
            logger.info(f"[STT] WebSocket URL full: {self.ws_url}")
            logger.info(f"[STT] Authentication: Using Authorization header (not URL token)")
            logger.info(f"[STT] Headers: Authorization={self.api_key[:10]}...")

            # Connect to WebSocket
            logger.info("[STT] Attempting WebSocket connection...")
            self.ws = await websockets.connect(
                self.ws_url,
                additional_headers={
                    "Authorization": self.api_key
                },
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )

            logger.info("[STT] WebSocket connection established")
            logger.info(f"[STT] WebSocket state: {self.ws.state}")

            # Wait for session start message
            try:
                logger.info("[STT] Waiting for session start message...")
                response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
                data = json.loads(response)

                logger.info(f"[STT] Received initial message: {data}")
                logger.info(f"[STT] Message keys: {list(data.keys())}")

                # Check for errors
                if "error" in data:
                    error_msg = data["error"]
                    logger.error(f"[STT] AssemblyAI error: {error_msg}")
                    logger.error(f"[STT] Full error data: {data}")
                    await self.close_session()
                    return False

                # Extract session ID if available
                if "session_id" in data:
                    self.session_id = data["session_id"]
                    logger.info(f"[STT] Session ID: {self.session_id}")
                else:
                    logger.warning("[STT] No session_id in initial message")

                # Update status
                self.is_running = True
                self.status = AgentStatus.LISTENING

                # Start background receive task
                self._receive_task = asyncio.create_task(self._receive_loop())

                logger.info("[STT] AssemblyAI session initialized successfully")
                return True

            except asyncio.TimeoutError:
                logger.error("[STT] Timeout waiting for session start message")
                logger.error("[STT] WebSocket state at timeout: {self.ws.state if self.ws else 'None'}")
                await self.close_session()
                return False

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"[STT] Invalid status code: {e.status_code}")
            logger.error(f"[STT] Response headers: {e.headers}")
            logger.error(f"[STT] Response body: {e.body}")
            if e.status_code == 401:
                logger.error("[STT] Authentication failed - check API key")
            elif e.status_code == 400:
                logger.error("[STT] Bad request - check API parameters")
            elif e.status_code == 403:
                logger.error("[STT] Forbidden - check permissions or quota")
            elif e.status_code == 404:
                logger.error("[STT] Endpoint not found - check URL")
            return False

        except websockets.exceptions.InvalidURI as e:
            logger.error(f"[STT] Invalid URI: {e}")
            logger.error(f"[STT] URL used: {self.ws_url}")
            return False

        except Exception as e:
            logger.error(f"[STT] Failed to initialize: {e}", exc_info=True)
            logger.error(f"[STT] Exception type: {type(e).__name__}")
            return False

    async def _receive_loop(self):
        """Background task to receive transcripts from AssemblyAI"""
        try:
            logger.info("[STT] Starting receive loop")
            while self.is_running and self.ws:
                try:
                    logger.debug("[STT] Waiting for message...")
                    message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                    logger.debug(f"[STT] Received message: {len(message)} chars")
                    await self._handle_message(message)

                except asyncio.TimeoutError:
                    logger.debug("[STT] Receive timeout (normal)")
                    continue

                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"[STT] WebSocket connection closed: {e}")
                    logger.warning(f"[STT] Close code: {e.code}, reason: {e.reason}")
                    break

                except Exception as e:
                    logger.error(f"[STT] Error receiving message: {e}")
                    logger.error(f"[STT] Exception type: {type(e).__name__}")
                    break

        except Exception as e:
            logger.error(f"[STT] Error in receive loop: {e}")
            logger.error(f"[STT] Exception type: {type(e).__name__}")
        finally:
            logger.info("[STT] Receive loop ended")

    async def _handle_message(self, message: str):
        """Handle incoming message from AssemblyAI"""
        try:
            data = json.loads(message)

            # Handle different message types
            message_type = data.get("message_type")

            if message_type == "PartialTranscript":
                # Partial (interim) transcript
                text = data.get("text", "")
                confidence = data.get("confidence", 0.0)

                if text and self.on_transcript_callback:
                    await self.on_transcript_callback({
                        "text": text,
                        "is_final": False,
                        "confidence": confidence,
                        "speaker": "Trainee"
                    })

            elif message_type == "FinalTranscript":
                # Final transcript
                text = data.get("text", "")
                confidence = data.get("confidence", 0.0)

                if text and self.on_transcript_callback:
                    logger.info(f"[STT] Final transcript: '{text}' (confidence: {confidence})")
                    await self.on_transcript_callback({
                        "text": text,
                        "is_final": True,
                        "confidence": confidence,
                        "speaker": "Trainee"
                    })

            elif message_type == "SessionBegins":
                logger.info(f"[STT] Session begins: {data}")
                self.session_id = data.get("session_id")

            elif message_type == "SessionTerminated":
                logger.info(f"[STT] Session terminated: {data}")
                self.is_running = False

            else:
                logger.debug(f"[STT] Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"[STT] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[STT] Error handling message: {e}")

    async def send_audio_base64(self, audio_base64: str):
        """
        Send base64-encoded audio data to AssemblyAI

        Args:
            audio_base64: Base64-encoded audio data
        """
        if not self.is_connected():
            logger.warning("[STT] Cannot send audio - not connected")
            logger.warning(f"[STT] Connection status: ws={self.ws is not None}, open={self.ws.open if self.ws else False}, running={self.is_running}")
            return

        try:
            # Decode base64 to bytes
            audio_bytes = base64.b64decode(audio_base64)
            logger.debug(f"[STT] Decoded base64 audio: {len(audio_bytes)} bytes")

            # Send binary audio data
            await self.ws.send(audio_bytes)

            logger.debug(f"[STT] Sent {len(audio_bytes)} bytes of audio")

        except Exception as e:
            logger.error(f"[STT] Error sending audio: {e}")
            logger.error(f"[STT] Exception type: {type(e).__name__}")

    async def send_audio_bytes(self, audio_bytes: bytes):
        """
        Send raw audio bytes to AssemblyAI

        Args:
            audio_bytes: Raw audio data as bytes
        """
        if not self.is_connected():
            logger.warning("[STT] Cannot send audio - not connected")
            logger.warning(f"[STT] Connection status: ws={self.ws is not None}, open={self.ws.open if self.ws else False}, running={self.is_running}")
            return

        try:
            logger.debug(f"[STT] Sending {len(audio_bytes)} bytes of raw audio")
            await self.ws.send(audio_bytes)
            logger.debug(f"[STT] Sent {len(audio_bytes)} bytes of audio")

        except Exception as e:
            logger.error(f"[STT] Error sending audio: {e}")
            logger.error(f"[STT] Exception type: {type(e).__name__}")

    async def close_session(self):
        """Close the AssemblyAI session"""
        logger.info("[STT] Closing AssemblyAI session...")
        logger.info(f"[STT] Current state: running={self.is_running}, ws={self.ws is not None}")

        self.is_running = False
        self.status = AgentStatus.IDLE

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            logger.info("[STT] Cancelling receive task...")
            self._receive_task.cancel()
            try:
                await asyncio.wait_for(self._receive_task, timeout=2.0)
                logger.info("[STT] Receive task cancelled successfully")
            except (asyncio.TimeoutError, asyncio.CancelledError) as e:
                logger.info(f"[STT] Receive task cancellation: {type(e).__name__}")
            except Exception as e:
                logger.error(f"[STT] Error cancelling receive task: {e}")

        # Close WebSocket
        if self.ws:
            try:
                logger.info(f"[STT] WebSocket state before close: {self.ws.state}")
                # Send terminate message
                await self.ws.send(json.dumps({"terminate_session": True}))
                await asyncio.sleep(0.1)  # Give it time to send

                await self.ws.close()
                logger.info("[STT] WebSocket closed successfully")
            except Exception as e:
                logger.debug(f"[STT] Error closing WebSocket: {e}")
                logger.debug(f"[STT] Exception type: {type(e).__name__}")
            finally:
                self.ws = None

        logger.info("[STT] AssemblyAI session closed")