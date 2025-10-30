import os
import asyncio
import logging
import json
import base64
from typing import Optional, Callable, Dict, Any, List
from livekit import api, rtc
# Note: livekit.agents imports temporarily commented out due to version compatibility
# from livekit.agents import llm, stt, tts, vad
from ..models.session import AgentStatus
from .groq_service import GroqService
from .assemblyai_service import AssemblyAIService
from .elevenlabs_service import ElevenLabsService

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
        self._on_message_callback: Optional[Callable] = None
        self._on_status_callback: Optional[Callable] = None
        self._on_transcript_callback: Optional[Callable] = None
        
        # AI Services
        self.groq_service: Optional[GroqService] = None
        self.stt_service: Optional[AssemblyAIService] = None
        self.tts_service: Optional[ElevenLabsService] = None
        
        # VAD and pipeline configuration
        self.vad_instance = None
        self.pipeline_agent = None

    async def initialize_session(
        self,
        room_name: str,
        persona_instruction: str,
        groq_api_key: str,
        assemblyai_api_key: str,
        elevenlabs_api_key: str,
        elevenlabs_voice_id: str,
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

            # Initialize AssemblyAI service
            logger.info("Initializing AssemblyAI service...")
            try:
                self.stt_service = AssemblyAIService(assemblyai_api_key)
                stt_success = await self.stt_service.initialize_realtime_session(
                    self._on_transcript_received,
                    self._on_service_error
                )
                if stt_success:
                    services_initialized.append("AssemblyAI")
                    logger.info("AssemblyAI service initialized successfully")
                else:
                    logger.warning("AssemblyAI service initialization returned False")
            except Exception as e:
                logger.error(f"Failed to initialize AssemblyAI service: {e}")
                logger.error(f"AssemblyAI API key length: {len(assemblyai_api_key) if assemblyai_api_key else 0}")
                self.stt_service = None

            # Initialize ElevenLabs service
            logger.info("Initializing ElevenLabs service...")
            try:
                self.tts_service = ElevenLabsService(elevenlabs_api_key, elevenlabs_voice_id)
                tts_success = await self.tts_service.initialize_session(
                    elevenlabs_voice_id,
                    self._on_audio_generated,
                    self._on_service_error
                )
                if tts_success:
                    services_initialized.append("ElevenLabs")
                    logger.info("ElevenLabs service initialized successfully")
                else:
                    logger.warning("ElevenLabs service initialization returned False")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs service: {e}")
                logger.error(f"ElevenLabs API key length: {len(elevenlabs_api_key) if elevenlabs_api_key else 0}")
                logger.error(f"ElevenLabs voice ID: {elevenlabs_voice_id}")
                self.tts_service = None

            # Check if at least one service is available
            if not services_initialized:
                logger.error("No AI services could be initialized - all services failed")
                raise Exception("No AI services could be initialized")

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

    async def _on_transcript_received(self, text: str, is_final: bool, confidence: Optional[float] = None):
        """Handle transcript from STT service"""
        try:
            if self._on_transcript_callback:
                await self._on_transcript_callback({
                    "text": text,
                    "is_final": is_final,
                    "confidence": confidence,
                    "speaker": "Trainee"
                })

            # If transcript is final, send to LLM
            if is_final and text.strip() and self.groq_service:
                self.status = AgentStatus.THINKING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)
                
                # Send to Groq LLM
                await self.groq_service.send_message(text)

        except Exception as e:
            logger.error(f"Error handling transcript: {e}")

    async def _on_llm_response(self, response: str, is_partial: bool = False):
        """Handle response from LLM service"""
        try:
            if self._on_transcript_callback:
                await self._on_transcript_callback({
                    "text": response,
                    "is_final": not is_partial,
                    "speaker": "AI Assistant"
                })

            # If response is complete, send to TTS
            if not is_partial and response.strip() and self.tts_service:
                self.status = AgentStatus.SPEAKING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)
                
                # Send to ElevenLabs TTS
                await self.tts_service.text_to_speech(response)

        except Exception as e:
            logger.error(f"Error handling LLM response: {e}")

    async def _on_audio_generated(self, audio_bytes: bytes, mime_type: str, is_stream: bool = False):
        """Handle generated audio from TTS service"""
        try:
            # Publish audio to LiveKit room
            if self.room and audio_bytes:
                await self._publish_audio_to_room(audio_bytes)

            # Also send via callback for WebSocket clients
            if self._on_message_callback:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                await self._on_message_callback({
                    "type": "audio",
                    "data": audio_base64,
                    "mime_type": mime_type
                })

            if not is_stream:  # Only update status when complete audio is generated
                self.status = AgentStatus.LISTENING
                if self._on_status_callback:
                    await self._on_status_callback(self.status)

        except Exception as e:
            logger.error(f"Error handling generated audio: {e}")

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
            if self.groq_service:
                await self.groq_service.send_message(text)
                return True
            logger.warning("Groq service not available")
            return False
        except Exception as e:
            logger.error(f"Failed to send text message: {e}")
            return False

    async def close_session(self):
        """Close the LiveKit orchestration session"""
        try:
            # Close AI services
            if self.groq_service:
                await self.groq_service.close_session()
            if self.stt_service:
                await self.stt_service.close_realtime_session()
            if self.tts_service:
                await self.tts_service.close_session()

            # Disconnect from room
            if self.room:
                await self.room.disconnect()
                self.room = None

            self.status = AgentStatus.IDLE
            logger.info("LiveKit orchestration session closed")

        except Exception as e:
            logger.error(f"Error closing LiveKit session: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def is_connected(self) -> bool:
        """Check if connected to LiveKit room"""
        return self.room is not None and self.room.connection_state == rtc.ConnectionState.CONN_CONNECTED