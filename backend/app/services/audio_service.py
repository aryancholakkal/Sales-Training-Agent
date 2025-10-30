import base64
import struct
import asyncio
import logging
from typing import Union, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class AudioService:
    """Enhanced audio service for LiveKit integration with multi-format support"""
    
    # Audio format constants
    SAMPLE_RATE_16K = 16000
    SAMPLE_RATE_48K = 48000
    CHANNELS_MONO = 1
    CHANNELS_STEREO = 2
    SAMPLE_WIDTH_16 = 2  # 16-bit = 2 bytes
    SAMPLE_WIDTH_24 = 3  # 24-bit = 3 bytes
    
    @staticmethod
    def encode(bytes_data: bytes) -> str:
        """Encode bytes to base64 string"""
        return base64.b64encode(bytes_data).decode('utf-8')
    
    @staticmethod
    def decode(base64_string: str) -> bytes:
        """Decode base64 string to bytes"""
        return base64.b64decode(base64_string)
    
    @staticmethod
    def create_audio_blob(data: Union[bytes, str], mime_type: str = 'audio/pcm;rate=16000') -> dict:
        """Create audio blob for API consumption"""
        if isinstance(data, bytes):
            encoded_data = AudioService.encode(data)
        else:
            encoded_data = data
            
        return {
            'data': encoded_data,
            'mimeType': mime_type
        }
    
    @staticmethod
    def process_float32_to_pcm(float32_data: list, sample_rate: int = SAMPLE_RATE_16K) -> bytes:
        """Convert Float32Array data to PCM bytes"""
        try:
            # Convert float32 values to int16 PCM
            int16_data = []
            for sample in float32_data:
                # Clamp to [-1, 1] and convert to int16
                clamped = max(-1.0, min(1.0, sample))
                int16_sample = int(clamped * 32767)
                int16_data.append(int16_sample)
            
            # Pack as little-endian 16-bit integers
            return struct.pack(f'<{len(int16_data)}h', *int16_data)
        except Exception as e:
            logger.error(f"Error converting float32 to PCM: {e}")
            return b""
    
    @staticmethod
    def process_pcm_to_float32(pcm_data: bytes) -> List[float]:
        """Convert PCM bytes to Float32 array"""
        try:
            # Unpack 16-bit little-endian integers
            int16_samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
            
            # Convert to float32 [-1, 1]
            float32_data = [sample / 32767.0 for sample in int16_samples]
            return float32_data
        except Exception as e:
            logger.error(f"Error converting PCM to float32: {e}")
            return []
    
    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
        """Resample audio data from one sample rate to another"""
        try:
            # Convert to numpy array for processing
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate resampling ratio
            ratio = to_rate / from_rate
            
            # Simple linear interpolation resampling
            new_length = int(len(audio_array) * ratio)
            resampled = np.interp(
                np.linspace(0, len(audio_array) - 1, new_length),
                np.arange(len(audio_array)),
                audio_array
            ).astype(np.int16)
            
            return resampled.tobytes()
        except Exception as e:
            logger.error(f"Error resampling audio: {e}")
            return audio_data  # Return original if resampling fails
    
    @staticmethod
    def convert_stereo_to_mono(stereo_data: bytes) -> bytes:
        """Convert stereo audio to mono by averaging channels"""
        try:
            # Unpack stereo samples (L, R, L, R, ...)
            samples = struct.unpack(f'<{len(stereo_data)//2}h', stereo_data)
            
            # Average left and right channels
            mono_samples = []
            for i in range(0, len(samples), 2):
                if i + 1 < len(samples):
                    mono_sample = (samples[i] + samples[i + 1]) // 2
                    mono_samples.append(mono_sample)
                else:
                    mono_samples.append(samples[i])
            
            return struct.pack(f'<{len(mono_samples)}h', *mono_samples)
        except Exception as e:
            logger.error(f"Error converting stereo to mono: {e}")
            return stereo_data
    
    @staticmethod
    def apply_gain(audio_data: bytes, gain_db: float) -> bytes:
        """Apply gain to audio data (in dB)"""
        try:
            # Convert dB to linear gain
            linear_gain = 10 ** (gain_db / 20.0)
            
            # Unpack audio samples
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            
            # Apply gain and clamp
            gained_samples = []
            for sample in samples:
                gained = int(sample * linear_gain)
                # Clamp to 16-bit range
                clamped = max(-32768, min(32767, gained))
                gained_samples.append(clamped)
            
            return struct.pack(f'<{len(gained_samples)}h', *gained_samples)
        except Exception as e:
            logger.error(f"Error applying gain: {e}")
            return audio_data
    
    @staticmethod
    def detect_silence(audio_data: bytes, threshold_db: float = -40.0, min_duration_ms: int = 500) -> bool:
        """Detect if audio contains silence"""
        try:
            # Unpack audio samples
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            
            if not samples:
                return True
            
            # Calculate RMS (Root Mean Square)
            rms = np.sqrt(np.mean(np.square(samples)))
            
            # Convert to dB
            if rms > 0:
                db_level = 20 * np.log10(rms / 32767.0)
            else:
                db_level = -np.inf
            
            return db_level < threshold_db
        except Exception as e:
            logger.error(f"Error detecting silence: {e}")
            return False
    
    @staticmethod
    def trim_silence(audio_data: bytes, threshold_db: float = -40.0) -> bytes:
        """Trim silence from beginning and end of audio"""
        try:
            # Unpack audio samples
            samples = list(struct.unpack(f'<{len(audio_data)//2}h', audio_data))
            
            if not samples:
                return audio_data
            
            # Find first non-silent sample
            start_idx = 0
            for i, sample in enumerate(samples):
                if abs(sample) > 32767 * (10 ** (threshold_db / 20.0)):
                    start_idx = i
                    break
            
            # Find last non-silent sample
            end_idx = len(samples) - 1
            for i in range(len(samples) - 1, -1, -1):
                if abs(samples[i]) > 32767 * (10 ** (threshold_db / 20.0)):
                    end_idx = i
                    break
            
            # Extract non-silent portion
            trimmed_samples = samples[start_idx:end_idx + 1]
            
            return struct.pack(f'<{len(trimmed_samples)}h', *trimmed_samples)
        except Exception as e:
            logger.error(f"Error trimming silence: {e}")
            return audio_data
    
    @staticmethod
    def chunk_audio(audio_data: bytes, chunk_size_ms: int = 100, sample_rate: int = SAMPLE_RATE_16K) -> List[bytes]:
        """Split audio data into chunks of specified duration"""
        try:
            # Calculate samples per chunk
            samples_per_chunk = (chunk_size_ms * sample_rate) // 1000
            bytes_per_chunk = samples_per_chunk * 2  # 16-bit = 2 bytes per sample
            
            chunks = []
            for i in range(0, len(audio_data), bytes_per_chunk):
                chunk = audio_data[i:i + bytes_per_chunk]
                if len(chunk) > 0:
                    chunks.append(chunk)
            
            return chunks
        except Exception as e:
            logger.error(f"Error chunking audio: {e}")
            return [audio_data]
    
    @staticmethod
    def merge_audio_chunks(chunks: List[bytes]) -> bytes:
        """Merge audio chunks into single audio data"""
        try:
            return b''.join(chunks)
        except Exception as e:
            logger.error(f"Error merging audio chunks: {e}")
            return b""
    
    @staticmethod
    def validate_audio_format(audio_data: bytes, expected_sample_rate: int = SAMPLE_RATE_16K) -> bool:
        """Validate audio format and quality"""
        try:
            if len(audio_data) == 0:
                return False
            
            # Check if length is valid for 16-bit samples
            if len(audio_data) % 2 != 0:
                return False
            
            # Basic validation - should contain some non-zero samples
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            non_zero_samples = sum(1 for sample in samples if sample != 0)
            
            # At least 1% of samples should be non-zero
            return (non_zero_samples / len(samples)) > 0.01
        except Exception as e:
            logger.error(f"Error validating audio format: {e}")
            return False
    
    @staticmethod
    def create_livekit_audio_frame(audio_data: bytes, sample_rate: int = SAMPLE_RATE_16K, channels: int = CHANNELS_MONO):
        """Create LiveKit compatible audio frame"""
        try:
            # This would be used with actual LiveKit audio frame creation
            # For now, return a dictionary with the required format
            return {
                'data': audio_data,
                'sample_rate': sample_rate,
                'channels': channels,
                'samples_per_channel': len(audio_data) // (2 * channels)  # 16-bit samples
            }
        except Exception as e:
            logger.error(f"Error creating LiveKit audio frame: {e}")
            return None
    
    @staticmethod
    async def process_audio_stream(audio_stream, chunk_processor, chunk_size_ms: int = 100):
        """Process continuous audio stream with chunking"""
        try:
            buffer = b""
            chunk_size_bytes = (chunk_size_ms * AudioService.SAMPLE_RATE_16K * 2) // 1000
            
            async for audio_chunk in audio_stream:
                buffer += audio_chunk
                
                # Process complete chunks
                while len(buffer) >= chunk_size_bytes:
                    chunk = buffer[:chunk_size_bytes]
                    buffer = buffer[chunk_size_bytes:]
                    
                    await chunk_processor(chunk)
                    
        except Exception as e:
            logger.error(f"Error processing audio stream: {e}")