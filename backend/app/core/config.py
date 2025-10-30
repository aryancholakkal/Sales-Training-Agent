import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    app_name: str = "AI Sales Training Backend"
    version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Configuration
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # AI Services Configuration
    # LiveKit Configuration (WebRTC/Real-time orchestration)
    livekit_api_key: str
    livekit_api_secret: str
    livekit_ws_url: str
    
    # AssemblyAI Configuration (Speech-to-Text)
    assemblyai_api_key: str
    
    # Groq Configuration (LLM)
    groq_api_key: str
    
    # ElevenLabs Configuration (Text-to-Speech)
    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Default voice ID (Adam)
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = 30
    ws_max_connections: int = 100
    
    # Audio Configuration
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 1024
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()