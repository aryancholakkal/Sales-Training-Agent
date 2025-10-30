import os
import asyncio
import logging
import json
import base64
from typing import Optional, Callable, Dict, Any
import assemblyai as aai
from ..models.session import AgentStatus

logger = logging.getLogger(__name__)


class AssemblyAIService:
    """Service for handling Speech-to-Text using AssemblyAI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        aai.settings.api_key = api_key
        self.transcriber = None
        self.status = AgentStatus.IDLE
        self._on_transcript_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._realtime_transcriber = None

    async def initialize_realtime_session(
        self,
        on_transcript_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None,
        sample_rate: int = 16000
    ) -> bool:
        """Initialize real-time transcription session"""
        try:
            self.status = AgentStatus.CONNECTING
            self._on_transcript_callback = on_transcript_callback
            self._on_error_callback = on_error_callback

            # Create real-time transcriber with updated API
            self._realtime_transcriber = aai.RealtimeTranscriber(
                on_data=self._on_realtime_data,
                on_error=self._on_realtime_error,
                on_open=self._on_realtime_open,
                on_close=self._on_realtime_close,
                sample_rate=sample_rate,
                word_boost=["sales", "training", "customer", "product", "price", "discount"],
                encoding=aai.AudioEncoding.pcm_s16le
            )

            # Connect to real-time service
            await asyncio.get_event_loop().run_in_executor(
                None, self._realtime_transcriber.connect
            )

            self.status = AgentStatus.LISTENING
            logger.info("AssemblyAI real-time session initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize AssemblyAI real-time session: {e}")
            self.status = AgentStatus.ERROR
            if on_error_callback:
                await on_error_callback(f"AssemblyAI initialization failed: {str(e)}")
            return False

    def _on_realtime_open(self, session_opened: aai.RealtimeSessionOpened):
        """Handle real-time session opened"""
        logger.info(f"AssemblyAI session opened: {session_opened.session_id}")

    def _on_realtime_close(self, session_closed):
        """Handle real-time session closed"""
        logger.info("AssemblyAI session closed")

    def _on_realtime_data(self, transcript: aai.RealtimeTranscript):
        """Handle real-time transcript data"""
        try:
            if isinstance(transcript, aai.RealtimeFinalTranscript):
                # Final transcript
                if transcript.text and self._on_transcript_callback:
                    asyncio.create_task(self._on_transcript_callback(
                        transcript.text,
                        is_final=True,
                        confidence=transcript.confidence if hasattr(transcript, 'confidence') else None
                    ))
            elif isinstance(transcript, aai.RealtimePartialTranscript):
                # Partial transcript
                if transcript.text and self._on_transcript_callback:
                    asyncio.create_task(self._on_transcript_callback(
                        transcript.text,
                        is_final=False,
                        confidence=transcript.confidence if hasattr(transcript, 'confidence') else None
                    ))
        except Exception as e:
            logger.error(f"Error processing real-time transcript: {e}")

    def _on_realtime_error(self, error: aai.RealtimeError):
        """Handle real-time transcription errors"""
        logger.error(f"AssemblyAI real-time error: {error}")
        if self._on_error_callback:
            asyncio.create_task(self._on_error_callback(str(error)))

    async def send_audio_data(self, audio_data: bytes) -> bool:
        """Send audio data for real-time transcription"""
        if not self._realtime_transcriber or self.status != AgentStatus.LISTENING:
            return False

        try:
            # Send audio data to AssemblyAI
            await asyncio.get_event_loop().run_in_executor(
                None, self._realtime_transcriber.stream, audio_data
            )
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
            if self._realtime_transcriber:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._realtime_transcriber.close
                )
                self._realtime_transcriber = None
            
            self.status = AgentStatus.IDLE
            logger.info("AssemblyAI real-time session closed")
        except Exception as e:
            logger.error(f"Error closing AssemblyAI session: {e}")

    async def pause_transcription(self):
        """Pause real-time transcription"""
        try:
            if self._realtime_transcriber:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._realtime_transcriber.force_end_utterance
                )
            logger.info("AssemblyAI transcription paused")
        except Exception as e:
            logger.error(f"Error pausing transcription: {e}")

    def get_status(self) -> AgentStatus:
        """Get current session status"""
        return self.status

    def is_connected(self) -> bool:
        """Check if real-time session is connected"""
        return self._realtime_transcriber is not None and self.status == AgentStatus.LISTENING