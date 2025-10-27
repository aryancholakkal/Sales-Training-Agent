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
    
    # GenAI Configuration
    gemini_api_key: str
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = 30
    ws_max_connections: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()