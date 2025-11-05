import asyncio
import websockets
import json
import base64
import logging
from typing import Optional, Callable
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class DeepgramService:
    """Deepgram Speech-to-Text service using WebSocket API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running = False
        self.status = AgentStatus.IDLE
        self.on_transcript_callback: Optional[Callable] = None
        self.session_id: Optional[str] = None

        # Deepgram WebSocket URL for real-time transcription
        # Use default model/params; tune as needed
        self.ws_url = (
            "wss://api.deepgram.com/v1/listen?encoding=linear16"
            "&sample_rate=16000&channels=1&model=nova-2&smart_format=true&interim_results=true"
        )

        # Background tasks and state
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._last_activity = 0.0
        self._connection_lost = asyncio.Event()
        self._connection_verified = asyncio.Event()

    def get_status(self) -> AgentStatus:
        """Get current service status"""
        return self.status

    def _ws_is_closed(self) -> bool:
        """Safely determine whether the underlying websocket appears closed.

        Different websocket implementations expose different attributes (e.g. `closed`,
        `is_closing`, `close_code`). Access them defensively to avoid AttributeError
        that previously crashed the receive loop when a Metadata message arrived.
        """
        if not self.ws:
            return True
        try:
            # Prefer boolean `closed` attribute when present
            if hasattr(self.ws, 'closed'):
                return bool(getattr(self.ws, 'closed'))

            # Some implementations expose `is_closing` as a method/property
            if hasattr(self.ws, 'is_closing'):
                val = getattr(self.ws, 'is_closing')
                return bool(val() if callable(val) else val)

            # Fallback: if a close code is present, treat as closed
            if hasattr(self.ws, 'close_code'):
                return getattr(self.ws, 'close_code') is not None

            # Unknown implementation - assume open (conservative)
            return False
        except Exception:
            logger.debug("[STT] Unable to introspect ws closed state; assuming open")
            return False

    def _ws_debug_info(self) -> dict:
        """Return a small snapshot of the websocket object's key attributes for debugging."""
        info = {
            "ws_present": bool(self.ws),
            "ws_type": str(type(self.ws)) if self.ws else None,
        }
        if not self.ws:
            return info

        try:
            candidates = [
                'closed', 'close_code', 'close_reason', 'is_closing',
                'state', 'ready_state', 'remote_address'
            ]
            for name in candidates:
                try:
                    val = getattr(self.ws, name)
                    # If callable, don't call here — just report it's callable
                    info[name] = 'callable' if callable(val) else val
                except Exception:
                    info[name] = None
        except Exception:
            pass

        return info

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        try:
            # Simplified connection check that focuses on the essential conditions
            ws_exists = self.ws is not None
            is_running = self.is_running
            not_closed = not self._ws_is_closed() if ws_exists else False

            connection_state = all([ws_exists, is_running, not_closed])
            
            # Log connection state for debugging
            if not connection_state:
                # Log a richer snapshot for debugging
                try:
                    logger.debug(f"[STT] Connection state check: ws_exists={ws_exists}, is_running={is_running}, not_closed={not_closed}, ws_info={self._ws_debug_info()}")
                except Exception:
                    logger.debug(f"[STT] Connection state check: ws_exists={ws_exists}, is_running={is_running}, not_closed={not_closed}, ws_type={type(self.ws)}")
            
            return connection_state
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            return False

    async def initialize_session(self, on_transcript_callback: Optional[Callable] = None) -> bool:
        """
        Initialize Deepgram streaming session

        Args:
            on_transcript_callback: Callback for transcript updates

        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("=== Deepgram Service Initialization ===")
            
            # Validate API key
            if not self.api_key:
                logger.error("[STT] No API key provided to Deepgram service")
                return False
            
            logger.info("[STT] API Key validation:")
            logger.info(f"- API Key length: {len(self.api_key)}")
            logger.info(f"- First 10 chars: {self.api_key[:10]}")
            
            self.on_transcript_callback = on_transcript_callback
            
            # Log connection attempt
            logger.info("[STT] Connection details:")
            logger.info(f"- WebSocket URL: {self.ws_url[:50]}...")
            logger.info("- Attempting connection with headers:")
            logger.info(f"  Authorization: Token {self.api_key[:5]}...")

            # Prepare headers with detailed logging
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json"
            }
            logger.info("[STT] Headers prepared for connection")

            # Connect to WebSocket with detailed error handling and connection verification
            try:
                # Attempt connection
                self.ws = await websockets.connect(
                    self.ws_url,
                    additional_headers=headers,  # Use additional_headers for websockets library
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                logger.info("[STT] WebSocket connection attempt successful")

                # Log a debug snapshot of the websocket object for diagnostics
                try:
                    logger.debug(f"[STT] WebSocket object after connect: {self._ws_debug_info()}")
                except Exception:
                    logger.debug(f"[STT] WebSocket object created: {type(self.ws)}")

                # Verify connection with a ping and allow connection to stabilize
                try:
                    pong_waiter = await self.ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=5.0)
                    logger.info("[STT] Connection verified with successful ping")
                    
                    # Add a small delay to ensure connection is fully established
                    await asyncio.sleep(0.5)
                    # NOTE: Avoid sending an empty binary frame here. Some STT
                    # servers (including Deepgram) treat an empty binary send as
                    # an end-of-stream marker and will immediately finalize the
                    # session (send Metadata then close). We rely on ping/pong
                    # for transport verification and will not send any test
                    # audio until actual audio frames arrive from the client.
                    logger.debug("[STT] Connection stabilized; skipping empty test send to avoid signaling EOF")
                except asyncio.TimeoutError:
                    logger.error("[STT] Connection verification failed - no pong received")
                    await self.ws.close()
                    self.ws = None
                    raise ConnectionError("Failed to verify WebSocket connection")
                except Exception as e:
                    logger.error(f"[STT] Connection verification failed: {e}")
                    try:
                        await self.ws.close()
                    except Exception:
                        pass
                    self.ws = None
                    raise
                
            except websockets.exceptions.InvalidStatusCode as e:
                logger.error(f"[STT] WebSocket connection failed with status {e.status_code}")
                raise
            except Exception as e:
                logger.error(f"[STT] WebSocket connection failed: {str(e)}")
                raise

            logger.info("[STT] WebSocket connection established and verified")

            # Update status and create persistent connection handler
            self.is_running = True
            self.status = AgentStatus.LISTENING

            # Start background receive task with error handling
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except (asyncio.CancelledError, Exception):
                    pass
                
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            def handle_task_completion(task):
                try:
                    # Check if the task failed
                    exc = task.exception()
                    if exc:
                        logger.error(f"[STT] Receive task failed: {exc}")
                        # Attempt to restart the receive task if still running
                        if self.is_running and not self.ws.closed:
                            logger.info("[STT] Restarting receive task...")
                            self._receive_task = asyncio.create_task(self._receive_loop())
                            self._receive_task.add_done_callback(handle_task_completion)
                except (asyncio.CancelledError, Exception) as e:
                    logger.error(f"[STT] Error in task completion handler: {e}")
            
            # Add completion callback to monitor task
            self._receive_task.add_done_callback(handle_task_completion)

            logger.info("[STT] Deepgram session initialized successfully")
            return True

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"[STT] Invalid status code: {e.status_code}")
            if e.status_code == 401:
                logger.error("[STT] Authentication failed - check API key")
                
            elif e.status_code == 400:
                logger.error("[STT] Bad request - check API parameters")
                
            elif e.status_code == 403:
                logger.error("[STT] Forbidden - check permissions or quota")
            elif e.status_code == 404:
                logger.error("[STT] Endpoint not found - check URL")
            return False

        except Exception as e:
            logger.error(f"[STT] Failed to initialize: {e}", exc_info=True)
            return False

    async def _receive_loop(self):
        """Background task to receive transcripts from Deepgram"""
        while self.is_running and self.ws:
            try:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                    # Update last activity timestamp
                    try:
                        self._last_activity = asyncio.get_event_loop().time()
                    except Exception:
                        pass
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    # No message received; send keep-alive ping (best-effort)
                    try:
                        pong = await self.ws.ping()
                        await asyncio.wait_for(pong, timeout=5.0)
                    except Exception:
                        logger.debug("[STT] Keep-alive ping failed during idle; continuing")
                        await asyncio.sleep(0.1)
                        continue
                except Exception as e:
                    # Attempt to detect websocket close and log any close code/reason
                    try:
                        # websockets library raises ConnectionClosed or ConnectionClosedError
                        # but different implementations may raise other types; log repr
                        logger.warning(f"[STT] Receive loop exception: {repr(e)}")
                        if hasattr(e, 'code') or hasattr(e, 'reason'):
                            logger.warning(f"[STT] Close details: code={getattr(e,'code',None)}, reason={getattr(e,'reason',None)}")
                    except Exception:
                        pass

                    # If the websocket itself reports closed, break
                    if self._ws_is_closed():
                        logger.warning("[STT] WebSocket connection closed (detected by ws state)")
                        break
                    # Otherwise sleep briefly and continue the loop
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"[STT] Error in receive loop: {e}")
                await asyncio.sleep(0.1)

        logger.info("[STT] Receive loop ended")

    async def _handle_message(self, message: str):
        """Handle incoming message from Deepgram"""
        try:
            data = json.loads(message)

            # Handle different message types
            if data.get("type") == "Results":
                # Extract transcript data
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])

                if alternatives:
                    transcript = alternatives[0].get("transcript", "")
                    confidence = alternatives[0].get("confidence", 0.0)
                    is_final = data.get("is_final", False)

                    if transcript and self.on_transcript_callback:
                        if is_final:
                            logger.info(f"[STT] Final transcript: '{transcript}' (confidence: {confidence})")
                        else:
                            logger.debug(f"[STT] Interim transcript: '{transcript}' (confidence: {confidence})")

                        await self.on_transcript_callback({
                            "text": transcript,
                            "is_final": is_final,
                            "confidence": confidence,
                            "speaker": "Trainee"
                        })

            elif data.get("type") == "Metadata":
                # Don't treat metadata message as a signal to close connection
                logger.info(f"[STT] Session metadata: {data}")
                # Keep the connection alive by sending a ping (defensive checks)
                if self.ws and not self._ws_is_closed():
                    try:
                        await self.ws.ping()
                    except Exception as e:
                        logger.error(f"[STT] Error sending keep-alive ping after metadata: {e}")

            elif data.get("type") == "Error":
                logger.error(f"[STT] Deepgram error: {data}")
                # For critical errors, attempt reconnection
                if "critical" in str(data).lower() or "invalid" in str(data).lower():
                    self.is_running = False
                    
            else:
                logger.debug(f"[STT] Unknown message type: {data.get('type')}")

        except json.JSONDecodeError as e:
            logger.error(f"[STT] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[STT] Error handling message: {e}")

    async def send_audio_base64(self, audio_base64: str, max_retries: int = 3) -> bool:
        """
        Send base64-encoded audio data to Deepgram with automatic reconnection

        Args:
            audio_base64: Base64-encoded audio data
            max_retries: Maximum number of reconnection attempts (default: 3)
        
        Returns:
            bool: True if audio was sent successfully, False otherwise
        """
        retry_count = 0
        initial_connection_attempt = True
        
        while retry_count <= max_retries:
            try:
                # Check connection status and attempt reconnection if needed
                if not self.is_connected():
                    if retry_count == max_retries:
                        logger.error("[STT] Max retries reached, giving up")
                        return False
                    
                    # Log more detailed information on first connection attempt
                    if initial_connection_attempt:
                        logger.info("[STT] Initial connection attempt - checking service state:")
                        logger.info(f"- WebSocket exists: {self.ws is not None}")
                        logger.info(f"- Is running: {self.is_running}")
                        logger.info(f"- Service status: {self.status}")
                        initial_connection_attempt = False
                    
                    logger.warning(f"[STT] Connection lost or not established, attempt {retry_count + 1}/{max_retries} to connect")
                    
                    try:
                        # Close existing connection if any
                        if self.ws:
                            await self.ws.close()
                            self.ws = None
                        
                        # Reset status
                        self.is_running = False
                        
                        # Attempt to reconnect
                        success = await self.initialize_session(self.on_transcript_callback)
                        if success:
                            logger.info("[STT] Reconnection successful")
                            # Add extra delay after successful reconnection
                            await asyncio.sleep(0.5)
                        else:
                            logger.error("[STT] Reconnection failed")
                            retry_count += 1
                            await asyncio.sleep(min(1.0 * retry_count, 5.0))  # Exponential backoff
                            continue
                            
                    except Exception as e:
                        logger.error(f"[STT] Error during reconnection: {e}")
                        retry_count += 1
                        await asyncio.sleep(min(1.0 * retry_count, 5.0))  # Exponential backoff
                        continue

                # Decode base64 to bytes
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                except Exception as e:
                    logger.error(f"[STT] Failed to decode base64 audio: {e}")
                    return False

                # Send binary audio data with connection state verification
                try:
                    # Verify connection is still alive before sending
                    if not self.ws or self._ws_is_closed():
                        raise ConnectionError("WebSocket not available for send")

                    await self.ws.send(audio_bytes)
                    logger.debug(f"[STT] Successfully sent {len(audio_bytes)} bytes of audio")
                    return True
                except (websockets.exceptions.ConnectionClosed, ConnectionError):
                    logger.warning("[STT] Connection closed while sending audio or not available")
                    self.is_running = False
                    retry_count += 1
                    continue
                    
                except Exception as e:
                    logger.error(f"[STT] Error sending audio data: {e}")
                    logger.error(f"Connection state: running={self.is_running}, ws_exists={self.ws is not None}")
                    retry_count += 1
                    # Force reconnection on next iteration
                    self.is_running = False
                    continue

            except Exception as e:
                logger.error(f"[STT] Unexpected error handling audio: {e}")
                retry_count += 1
                continue

        logger.error("[STT] Failed to send audio after all retries")
        return False

    async def send_audio_bytes(self, audio_bytes: bytes):
        """
        Send raw audio bytes to Deepgram

        Args:
            audio_bytes: Raw audio data as bytes
        """
        if not self.is_connected():
            logger.warning("[STT] Cannot send audio - not connected")
            return

        try:
            await self.ws.send(audio_bytes)
            logger.debug(f"[STT] Sent {len(audio_bytes)} bytes of audio")
            return True

        except Exception as e:
            logger.error(f"[STT] Error sending audio: {e}")
            return False

    async def close_session(self):
        """Close the Deepgram session"""
        logger.info("[STT] Closing Deepgram session...")

        self.is_running = False
        self.status = AgentStatus.IDLE

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await asyncio.wait_for(self._receive_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        # Close WebSocket
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.debug(f"[STT] Error closing WebSocket: {e}")
            finally:
                self.ws = None

        logger.info("[STT] Deepgram session closed")

    # Compatibility wrappers for alternate implementations
    async def initialize(self, on_transcript_callback: Optional[Callable] = None) -> bool:
        """Compatibility wrapper that calls initialize_session"""
        return await self.initialize_session(on_transcript_callback=on_transcript_callback)

    async def close(self) -> None:
        """Compatibility wrapper that calls close_session"""
        await self.close_session()