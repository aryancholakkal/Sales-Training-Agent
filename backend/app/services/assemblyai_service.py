import os
import asyncio
import logging
import json
import base64
from typing import Optional, Callable, Dict, Any
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class AssemblyAIService:
    """Service for handling Speech-to-Text using AssemblyAI Universal-Streaming"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        aai.settings.api_key = api_key
        self.transcriber = None
        self.status = AgentStatus.IDLE
        self._on_transcript_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._streaming_client = None
        self.loop = None

    async def initialize_realtime_session(
        self,
        on_transcript_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None,
        sample_rate: int = 16000
    ) -> bool:
        """Initialize real-time transcription session using Universal-Streaming"""
        try:
            self.status = AgentStatus.CONNECTING
            self._on_transcript_callback = on_transcript_callback
            self._on_error_callback = on_error_callback
            self.loop = asyncio.get_running_loop()

            # Create StreamingClient with new Universal-Streaming API
            self._streaming_client = StreamingClient(
                StreamingClientOptions(
                    api_key=self.api_key
                )
            )

            # Register event handlers
            self._streaming_client.on(StreamingEvents.Begin, self._on_begin)
            self._streaming_client.on(StreamingEvents.Turn, self._on_turn)
            self._streaming_client.on(StreamingEvents.Error, self._on_error)
            self._streaming_client.on(StreamingEvents.Termination, self._on_terminated)

            # Connect to the streaming service with parameters
            self._streaming_client.connect(
                StreamingParameters(
                    sample_rate=sample_rate,
                    encoding="pcm_s16le",
                    end_of_turn_confidence_threshold=0.7,
                    min_end_of_turn_silence_when_confident=500,  # milliseconds
                    max_turn_silence=2000,  # milliseconds
                    word_boost=["sales", "training", "customer", "product", "price", "discount"],
                    format_turns=True
                )
            )

            self.status = AgentStatus.LISTENING
            logger.info("AssemblyAI Universal-Streaming session initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize AssemblyAI streaming session: {e}")
            self.status = AgentStatus.ERROR
            if on_error_callback:
                await on_error_callback(f"AssemblyAI initialization failed: {str(e)}")
            return False

    def _on_begin(self, client: StreamingClient, event: BeginEvent):
        """Handle streaming session opened"""
        logger.info(f"AssemblyAI session opened: {event.id}")

    def _on_terminated(self, client: StreamingClient, event: TerminationEvent):
        """Handle streaming session terminated"""
        logger.info(f"AssemblyAI session terminated: {event.audio_duration_seconds}s processed")
        self.status = AgentStatus.IDLE

    def _on_turn(self, client: StreamingClient, event: TurnEvent):
        """Handle turn data (replaces the old transcript data handler)"""
        try:
            if not event.transcript:
                return
                
            # Universal-Streaming uses "turns" instead of transcripts
            # end_of_turn indicates if this is final
            is_final = event.end_of_turn
            
            if self._on_transcript_callback and self.loop:
                self.loop.create_task(self._on_transcript_callback(
                    event.transcript,
                    is_final=is_final,
                    confidence=event.end_of_turn_confidence if hasattr(event, 'end_of_turn_confidence') else None
                ))
        except Exception as e:
            logger.error(f"Error processing streaming turn: {e}")

    def _on_error(self, client: StreamingClient, error: StreamingError):
        """Handle streaming transcription errors"""
        logger.error(f"AssemblyAI streaming error: {error}")
        if self._on_error_callback and self.loop:
            self.loop.create_task(self._on_error_callback(str(error)))

    async def send_audio_data(self, audio_data: bytes) -> bool:
        """Send audio data for real-time transcription"""
        if not self._streaming_client or self.status != AgentStatus.LISTENING:
            return False

        try:
            # Send audio data to AssemblyAI
            self._streaming_client.stream(audio_data)
            return True
        except Exception as e:
            logger.error(f"Failed to send audio data to AssemblyAI: {e}")
            return False

    async def send_audio_base64(self, audio_base64: str) -> bool:
        """Send base64 encoded audio data for real-time transcription"""
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_base64)
            return await self.send_audio_data(audio_bytes)
        except Exception as e:
            logger.error(f"Failed to decode and send base64 audio: {e}")
            return False

    async def transcribe_file(self, file_path: str, **kwargs) -> Optional[str]:
        """Transcribe an audio file"""
        try:
            self.status = AgentStatus.SPEAKING
            
            # Configure transcription options
            config = aai.TranscriptionConfig(
                speech_model=kwargs.get('speech_model', aai.SpeechModel.best),
                language_code=kwargs.get('language_code', 'en'),
                punctuate=kwargs.get('punctuate', True),
                format_text=kwargs.get('format_text', True),
                word_boost=kwargs.get('word_boost', ["sales", "training", "customer", "product"]),
                boost_param=kwargs.get('boost_param', 'high'),
                filter_profanity=kwargs.get('filter_profanity', False),
                redact_pii=kwargs.get('redact_pii', False),
                speaker_labels=kwargs.get('speaker_labels', False)
            )

            # Create transcriber and transcribe
            transcriber = aai.Transcriber(config=config)
            transcript = await asyncio.get_event_loop().run_in_executor(
                None, transcriber.transcribe, file_path
            )

            self.status = AgentStatus.LISTENING

            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Transcription failed: {transcript.error}")
                return None

            logger.info(f"File transcription completed: {len(transcript.text)} characters")
            return transcript.text

        except Exception as e:
            logger.error(f"Failed to transcribe file: {e}")
            self.status = AgentStatus.ERROR
            return None

    async def transcribe_url(self, audio_url: str, **kwargs) -> Optional[str]:
        """Transcribe audio from URL"""
        try:
            self.status = AgentStatus.SPEAKING
            
            # Configure transcription options
            config = aai.TranscriptionConfig(
                speech_model=kwargs.get('speech_model', aai.SpeechModel.best),
                language_code=kwargs.get('language_code', 'en'),
                punctuate=kwargs.get('punctuate', True),
                format_text=kwargs.get('format_text', True),
                word_boost=kwargs.get('word_boost', ["sales", "training", "customer", "product"]),
                boost_param=kwargs.get('boost_param', 'high'),
                filter_profanity=kwargs.get('filter_profanity', False),
                redact_pii=kwargs.get('redact_pii', False),
                speaker_labels=kwargs.get('speaker_labels', False)
            )

            # Create transcriber and transcribe
            transcriber = aai.Transcriber(config=config)
            transcript = await asyncio.get_event_loop().run_in_executor(
                None, transcriber.transcribe, audio_url
            )

            self.status = AgentStatus.LISTENING

            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Transcription failed: {transcript.error}")
                return None

            logger.info(f"URL transcription completed: {len(transcript.text)} characters")
            return transcript.text

        except Exception as e:
            logger.error(f"Failed to transcribe URL: {e}")
            self.status = AgentStatus.ERROR
            return None

    async def close_realtime_session(self):
        """Close the real-time transcription session"""
        try:
            if self._streaming_client:
                self._streaming_client.disconnect()
                self._streaming_client = None
            
            self.status = AgentStatus.IDLE
            logger.info("AssemblyAI streaming session closed")
        except Exception as e:
            logger.error(f"Error closing AssemblyAI session: {e}")

    async def pause_transcription(self):
        """Pause real-time transcription (force end current utterance)"""
        try:
            if self._streaming_client:
                self._streaming_client.force_end_utterance()
            logger.info("AssemblyAI transcription paused")
        except Exception as e:
            logger.error(f"Error pausing transcription: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def is_connected(self) -> bool:
        """Check if streaming session is connected"""
        return self._streaming_client is not None and self.status == AgentStatus.LISTENING