import os
import asyncio
import logging
import json
import base64
import time
from typing import Optional, Callable, Dict, Any, List
from livekit import api, rtc
# Note: livekit.agents imports temporarily commented out due to version compatibility
# from livekit.agents import llm, stt, tts, vad
from ..models.session import AgentStatus
from ..core.config import get_settings
from .groq_service import GroqService
from .deepgram_service import DeepgramService
from .openai_service import OpenAITTSService

logger = logging.getLogger(__name__)


class LiveKitOrchestrationService:
    """Service for orchestrating real-time conversations using LiveKit with VAD and turn detection"""

    def __init__(self, api_key: str, api_secret: str, ws_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url
        self.room = None
        self.agent = None
        self.status = AgentStatus.IDLE
        self._is_active = True
        self._on_message_callback: Optional[Callable] = None
        self._on_status_callback: Optional[Callable] = None
        self._on_transcript_callback: Optional[Callable] = None

        # AI Services
        self.groq_service: Optional[GroqService] = None
        self.stt_service: Optional[DeepgramService] = None
        self.tts_service: Optional[OpenAITTSService] = None

        # VAD and pipeline configuration
        self.vad_instance = None
        self.pipeline_agent = None

        # Conversation state helpers
        self._user_message_lock = asyncio.Lock()
        self._last_final_user_text: Optional[str] = None
        self._last_ai_response: Optional[str] = None
        self._last_user_final_ts: float = 0.0
        self._current_tts_task: Optional[asyncio.Task] = None
        self._tts_interrupting: bool = False

        # Deferred user processing to handle natural pauses
        self._settings = get_settings()
        pause_ms = max(self._settings.user_pause_ms, 0)
        self._user_pause_delay = max(0.1, pause_ms / 1000.0)
        self._pending_user_task: Optional[asyncio.Task] = None
        self._pending_user_transcripts: Dict[int, str] = {}
        self._pending_user_order: List[int] = []

    async def initialize_session(
        self,
        room_name: str,
        persona_instruction: str,
        groq_api_key: str,
        deepgram_api_key: str,
        openai_api_key: str,
        openai_tts_voice: str,
        on_message_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        on_transcript_callback: Optional[Callable] = None
    ) -> bool:
        """Initialize LiveKit orchestration session"""
        try:
            logger.info("Starting LiveKit orchestration session initialization")
            self.status = AgentStatus.CONNECTING
            if on_status_callback:
                await on_status_callback(self.status)

            # Store callbacks
            self._on_message_callback = on_message_callback
            self._on_status_callback = on_status_callback
            self._on_transcript_callback = on_transcript_callback
            self.reset_turn_state()

            # Initialize AI services with error handling
            services_initialized = []

            # Initialize Groq service
            logger.info("Initializing Groq service...")
            try:
                self.groq_service = GroqService(groq_api_key)
                groq_success = await self.groq_service.initialize_session(
                    persona_instruction,
                    self._on_llm_response,
                    self._on_service_status_change
                )
                if groq_success:
                    services_initialized.append("Groq")
                    logger.info("Groq service initialized successfully")
                else:
                    logger.warning("Groq service initialization returned False")
            except Exception as e:
                logger.error(f"Failed to initialize Groq service: {e}")
                logger.error(f"Groq API key length: {len(groq_api_key) if groq_api_key else 0}")
                self.groq_service = None

            # Initialize Deepgram service
            logger.info("Initializing Deepgram service...")
            try:
                # More detailed logging for API key
                api_key_length = len(deepgram_api_key) if deepgram_api_key else 0
                logger.info(f"Deepgram API key check - Length: {api_key_length}, First 4 chars: {deepgram_api_key[:4] if api_key_length > 4 else 'N/A'}")
                
                if not deepgram_api_key or api_key_length == 0:
                    logger.error("Deepgram API key is missing or empty")
                    raise ValueError("Deepgram API key is required")
                
                # Create service instance
                self.stt_service = DeepgramService(
                    deepgram_api_key,
                    extra_query_params=self._settings.deepgram_stream_params,
                )
                logger.info("Deepgram service instance created successfully")

                # Initialize session with detailed error reporting
                try:
                    stt_success = await self.stt_service.initialize(
                        on_transcript_callback=self._on_transcript_received
                    )
                    logger.info(f"Deepgram initialization result: {stt_success}")
                except Exception as init_error:
                    logger.error(f"Deepgram initialization error: {str(init_error)}")
                    raise

                if stt_success:
                    try:
                        # Check connection status with safer attribute access
                        is_connected = self.stt_service.is_connected()
                        status = self.stt_service.get_status()
                        
                        logger.info(f"Deepgram Status Check:")
                        logger.info(f"- Connected: {is_connected}")
                        logger.info(f"- Service Status: {status}")
                        logger.info(f"- WebSocket State: {'CONNECTED' if is_connected else 'DISCONNECTED'}")

                        if is_connected:
                            services_initialized.append("Deepgram")
                            logger.info("✓ Deepgram service initialized and connected successfully")
                        else:
                            logger.warning("⚠ Deepgram service initialized but not connected")
                            logger.error("Connection failed after initialization")
                            # Keep service instance for potential reconnection
                            logger.warning("Keeping Deepgram service instance for potential reconnection")
                    except Exception as e:
                        logger.error(f"Error checking Deepgram connection: {e}")
                        logger.error("Continuing with degraded STT functionality")
                else:
                    logger.error("✗ Deepgram service initialization failed")
                    logger.error(f"Service status: {self.stt_service.get_status() if self.stt_service else 'No service instance'}")
                    self.stt_service = None
            except Exception as e:
                logger.error(f"Failed to initialize Deepgram service: {e}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                self.stt_service = None

            # Initialize OpenAI TTS service for AI responses
            logger.info("Initializing OpenAI TTS service for AI...")
            try:
                self.tts_service = OpenAITTSService(openai_api_key, openai_tts_voice)
                tts_success = await self.tts_service.initialize_session(
                    voice=openai_tts_voice,
                    model="tts-1",
                    on_audio_callback=self._on_audio_generated,
                    on_error_callback=self._on_service_error
                )
                if tts_success:
                    services_initialized.append("OpenAI TTS (AI)")
                    logger.info("OpenAI TTS service for AI initialized successfully")
                else:
                    logger.warning("OpenAI TTS service for AI initialization returned False")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI TTS service for AI: {e}")
                logger.error(f"OpenAI API key length: {len(openai_api_key) if openai_api_key else 0}")
                logger.error(f"OpenAI TTS voice: {openai_tts_voice}")
                self.tts_service = None

            # Check if required services are available (Groq and AI TTS)
            if not services_initialized or "Groq" not in services_initialized:
                logger.error("No AI services could be initialized - Groq is required")
                raise Exception("Groq service is required for the system to work")

            logger.info(f"Successfully initialized services: {', '.join(services_initialized)}")

            # Create room and connect
            await self._create_and_connect_room(room_name)
            
            # Note: VAD and pipeline features temporarily disabled due to import issues
            logger.info("VAD and pipeline features disabled - using direct service integration")

            self.status = AgentStatus.LISTENING
            if on_status_callback:
                await on_status_callback(self.status)

            logger.info(f"LiveKit orchestration session initialized for room: {room_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LiveKit session: {e}")
            self.status = AgentStatus.ERROR
            if on_status_callback:
                await on_status_callback(self.status)
            return False

    async def _create_and_connect_room(self, room_name: str):
        """Create and connect to LiveKit room"""
        try:
            # Skip room connection for now - focus on service integration
            logger.info(f"Skipping LiveKit room connection for room: {room_name} - using direct service integration")

        except Exception as e:
            logger.error(f"Failed to create/connect to room: {e}")
            raise

    # Voice pipeline setup temporarily disabled due to import issues
    # async def _setup_voice_pipeline(self, system_prompt: str):
    #     """Setup the voice pipeline agent with VAD and turn detection"""
    #     # Implementation disabled until livekit.agents.pipeline is available
    #     pass

    async def _on_participant_connected(self, participant: rtc.RemoteParticipant):
        """Handle participant connection"""
        logger.info(f"Participant connected: {participant.identity}")
        
        if self._on_message_callback:
            await self._on_message_callback(f"Participant {participant.identity} joined the session")

    async def _on_participant_disconnected(self, participant: rtc.RemoteParticipant):
        """Handle participant disconnection"""
        logger.info(f"Participant disconnected: {participant.identity}")
        
        if self._on_message_callback:
            await self._on_message_callback(f"Participant {participant.identity} left the session")

    async def _on_track_published(self, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Handle track publication"""
        logger.info(f"Track published: {publication.sid} by {participant.identity}")

    async def _on_track_subscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Handle track subscription - this is where we process audio"""
        logger.info(f"Track subscribed: {track.sid} from {participant.identity}")
        
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            # Start processing audio from this track
            await self._process_audio_track(track)

    async def _process_audio_track(self, track: rtc.AudioTrack):
        """Process incoming audio track for STT"""
        try:
            # Create audio stream
            audio_stream = rtc.AudioStream(track)
            
            # Process audio frames
            async for frame in audio_stream:
                # Convert audio frame to bytes and send to STT
                audio_data = frame.data.tobytes()
                if self.stt_service:
                    await self.stt_service.send_audio_data(audio_data)
                    
        except Exception as e:
            logger.error(f"Error processing audio track: {e}")

    async def _on_track_unsubscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Handle track unsubscription"""
        logger.info(f"Track unsubscribed: {track.sid} from {participant.identity}")

    async def _on_transcript_received(self, transcript_data: dict):
        """Handle transcript from STT service"""
        try:
            if not self._is_active:
                return

            raw_text = transcript_data.get("text", "")
            text = raw_text.strip()
            is_final = transcript_data.get("is_final", False)
            confidence = transcript_data.get("confidence")

            log_message = f"[STT] Received transcript in LiveKit service: '{raw_text}' (final: {is_final}, confidence: {confidence})"
            if is_final:
                logger.info(log_message)
            else:
                logger.debug(log_message)

            if transcript_data.get("speaker") == "Trainee":
                if not is_final and text:
                    if self.is_ai_speaking():
                        await self.interrupt_ai_speech("trainee_started_speaking")
                    self._schedule_user_processing(text, transcript_data.get("id"))
                elif is_final and text:
                    self._finalize_user_processing(text, transcript_data.get("id"))

                if self._on_transcript_callback:
                    await self._on_transcript_callback({
                        "text": raw_text,
                        "is_final": is_final,
                        "confidence": confidence,
                        "speaker": "Trainee"
                    })
                else:
                    logger.debug("[WebSocket] No transcript callback available")
                return

            if self._on_transcript_callback:
                await self._on_transcript_callback({
                    "text": raw_text,
                    "is_final": is_final,
                    "confidence": confidence,
                    "speaker": "Customer"
                })

        except Exception as e:
            logger.error(f"Error handling transcript: {e}")

    async def _handle_final_user_transcript(self, text: str):
        """Ensure final user transcripts are processed sequentially."""
        try:
            async with self._user_message_lock:
                if not self._is_active:
                    return

                if not self.groq_service:
                    logger.warning("[LLM] Groq service not available")
                    return

                logger.info(f"[LLM] Processing trainee message: '{text}'")
                self.status = AgentStatus.THINKING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)

                await self.groq_service.stream_message(text)

        except Exception as e:
            logger.error(f"Error while handling final transcript: {e}")

    def _resolve_transcript_id(self, transcript_id: Optional[Any]) -> int:
        if isinstance(transcript_id, int):
            return transcript_id
        if isinstance(transcript_id, str):
            if transcript_id.isdigit():
                return int(transcript_id)
            return abs(hash(transcript_id))
        if transcript_id is None:
            # Deepgram real-time transcripts often omit an identifier for the
            # current utterance; treat them as a single rolling buffer per
            # speaker so partial packets overwrite the pending text instead of
            # queueing multiple LLM turns.
            return 0
        return abs(hash(str(transcript_id)))

    def _schedule_user_processing(self, transcript: str, transcript_id: Optional[Any]):
        resolved_id = self._resolve_transcript_id(transcript_id)

        self._pending_user_transcripts[resolved_id] = transcript
        if resolved_id not in self._pending_user_order:
            self._pending_user_order.append(resolved_id)

        self._start_user_dispatch_timer()

    def _finalize_user_processing(self, transcript: str, transcript_id: Optional[Any]):
        resolved_id = self._resolve_transcript_id(transcript_id)

        self._pending_user_transcripts[resolved_id] = transcript
        if resolved_id not in self._pending_user_order:
            self._pending_user_order.append(resolved_id)

        # Final transcripts still wait for the configured pause window to avoid
        # interrupting trainees who continue speaking after brief silences.
        self._start_user_dispatch_timer()

    def _start_user_dispatch_timer(self, delay: Optional[float] = None):
        wait_seconds = self._user_pause_delay if delay is None else max(0.0, delay)

        if self._pending_user_task is not None and not self._pending_user_task.done():
            self._pending_user_task.cancel()

        self._pending_user_task = asyncio.create_task(self._deferred_user_dispatch(wait_seconds))

    async def _deferred_user_dispatch(self, wait_seconds: float):
        current_task = asyncio.current_task()
        try:
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            if not self._is_active or not self._pending_user_order:
                return

            transcript_id = self._pending_user_order.pop(0)
            transcript_text = self._pending_user_transcripts.pop(transcript_id, "").strip()

            if not transcript_text:
                return

            now = time.monotonic()
            if transcript_text == self._last_final_user_text and (now - self._last_user_final_ts) < 0.5:
                logger.debug("[LLM] Skipping duplicate deferred transcript")
                return

            self._last_final_user_text = transcript_text
            self._last_user_final_ts = now
            await self._handle_final_user_transcript(transcript_text)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Error in deferred user dispatch: {exc}")
        finally:
            if self._pending_user_task is current_task:
                self._pending_user_task = None
                if self._pending_user_order and self._is_active:
                    # Additional messages that accumulated while we were waiting
                    # should process without an extra pause.
                    self._start_user_dispatch_timer(delay=0.0)

    def reset_turn_state(self):
        """Clear cached turn tracking data for a fresh conversation."""
        self._last_final_user_text = None
        self._last_ai_response = None
        self._last_user_final_ts = 0.0
        if self._pending_user_task is not None and not self._pending_user_task.done():
            self._pending_user_task.cancel()
        self._pending_user_task = None
        self._pending_user_transcripts.clear()
        self._pending_user_order.clear()

    def is_ai_speaking(self) -> bool:
        """Return True when the AI is currently streaming speech audio."""
        task_active = self._current_tts_task is not None and not self._current_tts_task.done()
        tts_active = self.tts_service is not None and self.tts_service.is_streaming()
        return task_active or tts_active

    async def interrupt_ai_speech(self, reason: str = "user_started_speaking") -> bool:
        """Stop current AI speech playback when the user interrupts."""
        if not self.is_ai_speaking():
            return False

        if self._tts_interrupting:
            return False

        self._tts_interrupting = True
        try:
            logger.info(f"[TTS] Interrupt requested: {reason}")
            stopped = await self._stop_tts_playback(reason=reason, notify_client=True)
            return stopped
        finally:
            self._tts_interrupting = False

    async def _stop_tts_playback(self, reason: str, notify_client: bool, update_status: bool = True) -> bool:
        """Stop any active TTS playback task and optionally notify the client."""
        task = self._current_tts_task
        stream_active = self.tts_service is not None and self.tts_service.is_streaming()

        if task is None and not stream_active:
            return False

        if self.tts_service is not None:
            try:
                await self.tts_service.stop_stream(reason=reason)
            except Exception as e:
                logger.error(f"Error requesting TTS stream stop: {e}")

        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

        self._current_tts_task = None

        if notify_client and self._on_message_callback:
            try:
                await self._on_message_callback({
                    "type": "audio_stop",
                    "reason": reason
                })
            except Exception as e:
                logger.error(f"Error notifying client about audio stop: {e}")

        if update_status and self._is_active:
            self.status = AgentStatus.LISTENING
            if self._on_status_callback:
                await self._on_status_callback(self.status)

        return True

    async def _start_tts_stream(self, text: str):
        """Start streaming TTS audio for the provided text."""
        if not self.tts_service:
            logger.warning("[TTS] AI TTS service not available for response")
            if self._is_active:
                self.status = AgentStatus.LISTENING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)
            return

        await self._stop_tts_playback(reason="replace_ai_tts", notify_client=False, update_status=False)

        async def run_tts():
            task_ref = asyncio.current_task()
            try:
                await self.tts_service.stream_text_to_speech(text)
            except asyncio.CancelledError:
                logger.info("[TTS] Streaming task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error during TTS streaming: {e}")
            finally:
                if self._current_tts_task is task_ref:
                    self._current_tts_task = None
                if self._is_active and self.status != AgentStatus.ERROR:
                    self.status = AgentStatus.LISTENING
                    if self._on_status_callback:
                        await self._on_status_callback(self.status)

        self.status = AgentStatus.SPEAKING
        if self._on_status_callback:
            await self._on_status_callback(self.status)

        self._current_tts_task = asyncio.create_task(run_tts())

    async def _on_llm_response(self, response: str, is_partial: bool = False):
        """Handle response from LLM service"""
        try:
            if not self._is_active:
                return

            logger.info(f"[LLM] Received response: '{response}' (partial: {is_partial})")

            if self._on_transcript_callback:
                await self._on_transcript_callback({
                    "text": response,
                    "is_final": not is_partial,
                    "speaker": "AI Assistant"
                })

            if is_partial:
                # Reset last AI response marker while streaming chunks
                self._last_ai_response = None
                return

            final_response = response.strip()
            if not final_response:
                return

            if final_response == self._last_ai_response:
                logger.debug("[TTS] Duplicate final AI response detected, skipping speech generation")
                return

            self._last_ai_response = final_response

            if self.tts_service:
                logger.info(f"[TTS] Generating AI speech for response: '{final_response}'")
                await self._start_tts_stream(final_response)
            else:
                logger.warning("[TTS] AI TTS service not available for response")
                self.status = AgentStatus.LISTENING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)

        except Exception as e:
            logger.error(f"Error handling LLM response: {e}")


    async def _on_audio_generated(self, audio_bytes: bytes, mime_type: str, is_stream: bool = False, bit_rate: Optional[int] = None, codec: Optional[str] = None, sample_rate: Optional[int] = None, channels: Optional[int] = None, bit_depth: Optional[int] = None, encoding: Optional[str] = None):
        """Handle generated audio from AI TTS service"""
        try:
            if not self._is_active:
                return

            logger.info(f"[TTS] AI audio generated: {len(audio_bytes)} bytes, mime_type: {mime_type}, is_stream: {is_stream}")

            # Publish audio to LiveKit room
            if self.room and audio_bytes:
                await self._publish_audio_to_room(audio_bytes)

            # Also send via callback for WebSocket clients
            if self._on_message_callback:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                logger.info(f"[WebSocket] Sending AI audio to client: {len(audio_base64)} base64 chars")
                # Use provided metadata when available, otherwise sensible defaults
                resolved_mime = mime_type or "audio/mpeg"
                resolved_sample_rate = sample_rate or (24000 if "mp3" in resolved_mime or "mpeg" in resolved_mime else 16000)
                resolved_channels = channels or 1
                resolved_bit_rate = bit_rate or 192000
                resolved_codec = codec or ("mp3" if "mp3" in resolved_mime or "mpeg" in resolved_mime else None)
                resolved_bit_depth = bit_depth
                resolved_encoding = encoding
                await self._on_message_callback({
                    "type": "audio",
                    "data": audio_base64,
                    "mime_type": resolved_mime,
                    "sample_rate": resolved_sample_rate,
                    "channels": resolved_channels,
                    "bit_rate": resolved_bit_rate,
                    "codec": resolved_codec,
                    "bit_depth": resolved_bit_depth,
                    "encoding": resolved_encoding,
                    "speaker": "AI Assistant"
                })

            if not is_stream:  # Only update status when complete audio is generated
                logger.info("[Status] AI finished speaking, setting status to listening")
                self.status = AgentStatus.LISTENING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)

        except Exception as e:
            logger.error(f"Error handling AI generated audio: {e}")

    async def _publish_audio_to_room(self, audio_bytes: bytes):
        """Publish audio to LiveKit room"""
        try:
            # Create audio track and publish
            # Note: This is a simplified version - actual implementation may need
            # proper audio format conversion and streaming
            pass  # Placeholder for actual audio publishing logic
        except Exception as e:
            logger.error(f"Error publishing audio to room: {e}")

    async def _on_service_status_change(self, status: AgentStatus):
        """Handle status changes from AI services"""
        # Aggregate status from all services
        if status == AgentStatus.ERROR:
            self.status = AgentStatus.ERROR
        else:
            # Check status of available services only
            available_services = [service for service in [self.groq_service, self.stt_service, self.tts_service] if service is not None]
            if available_services and all(service.get_status() != AgentStatus.ERROR for service in available_services):
                self.status = status

        if self._on_status_callback:
            await self._on_status_callback(self.status)

    async def _on_service_error(self, error_message: str):
        """Handle errors from AI services"""
        logger.error(f"AI service error: {error_message}")
        self.status = AgentStatus.ERROR
        if self._on_status_callback:
            await self._on_status_callback(self.status)

    async def send_text_message(self, text: str) -> bool:
        """Send a text message through the pipeline"""
        try:
            if not self._is_active:
                return False

            # Send to Groq LLM with streaming
            if self.groq_service:
                await self.groq_service.stream_message(text)
                return True
            logger.warning("Groq service not available")
            return False
        except Exception as e:
            logger.error(f"Failed to send text message: {e}")
            return False

    async def cleanup(self):
        """Clean up all services in proper order"""
        # Stop accepting new messages
        self._is_active = False

        try:
            await self._stop_tts_playback("cleanup", notify_client=True, update_status=False)
        except Exception as e:
            logger.error(f"Error stopping TTS during cleanup: {e}")

        # Add small delay to let fast pending operations complete (protected)
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Propagate cancellation so shutdown proceeds immediately
            logger.info("Cleanup interrupted during initial sleep; re-raising CancelledError")
            raise

        logger.info("Starting service cleanup...")

        # Wrap each service closure so a CancelledError in one doesn't prevent other cleanups
        try:
            # 1. Stop accepting new audio first
            if self.stt_service:
                try:
                    logger.info("Closing Deepgram service...")
                    await asyncio.wait_for(self.stt_service.close(), timeout=3.0)
                except asyncio.CancelledError:
                    logger.info("Deepgram close was cancelled; re-raising CancelledError")
                    raise
                except Exception as e:
                    logger.error(f"Error closing Deepgram service: {e}")

            # 2. Wait briefly for any pending TTS operations (protected from cancellation)
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                logger.info("Cleanup sleep interrupted; continuing with remaining shutdown steps")

            # 3. Close TTS services
            if self.tts_service:
                try:
                    await self.tts_service.close_session()
                except asyncio.CancelledError:
                    logger.info("TTS close was cancelled; re-raising CancelledError")
                    raise
                except Exception as e:
                    logger.error(f"Error closing TTS service: {e}")

            # 4. Finally close LLM
            if self.groq_service:
                try:
                    logger.info("Closing Groq service...")
                    await self.groq_service.close_session()
                except asyncio.CancelledError:
                    logger.info("Groq close was cancelled; re-raising CancelledError")
                    raise
                except Exception as e:
                    logger.error(f"Error closing Groq service: {e}")

            logger.info("All services cleaned up (best-effort)")
            self.reset_turn_state()

        except asyncio.CancelledError:
            # Ensure cancellation propagates to the caller so the runtime can shut down quickly
            logger.info("Cleanup received CancelledError; re-raising to allow immediate shutdown")
            raise
        except asyncio.TimeoutError:
            logger.warning("Service cleanup timed out, forcing shutdown")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def close_session(self):
        """Close the LiveKit orchestration session"""
        try:
            # Use the new cleanup method for proper shutdown order
            await self.cleanup()

            # Disconnect from room
            if self.room:
                await self.room.disconnect()
                self.room = None

            self.status = AgentStatus.IDLE
            logger.info("LiveKit orchestration session closed")

        except Exception as e:
            # If the close was cancelled, re-raise to allow shutdown to proceed
            if isinstance(e, asyncio.CancelledError):
                logger.info("close_session cancelled; re-raising CancelledError")
                raise
            logger.error(f"Error closing LiveKit session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def is_connected(self) -> bool:
        """Check if connected to LiveKit room"""
        return self.room is not None and self.room.connection_state == rtc.ConnectionState.CONN_CONNECTED