import base64
from typing import Union


class AudioService:
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
        """Create audio blob for GenAI"""
        if isinstance(data, bytes):
            encoded_data = AudioService.encode(data)
        else:
            encoded_data = data
            
        return {
            'data': encoded_data,
            'mimeType': mime_type
        }
    
    @staticmethod
    def process_float32_to_pcm(float32_data: list) -> bytes:
        """Convert Float32Array data to PCM bytes"""
        import struct
        
        # Convert float32 values to int16 PCM
        int16_data = []
        for sample in float32_data:
            # Clamp to [-1, 1] and convert to int16
            clamped = max(-1.0, min(1.0, sample))
            int16_sample = int(clamped * 32767)
            int16_data.append(int16_sample)
        
        # Pack as little-endian 16-bit integers
        return struct.pack(f'<{len(int16_data)}h', *int16_data)