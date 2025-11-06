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
    
    # Deepgram Configuration (Speech-to-Text)
    deepgram_api_key: str
    
    # Groq Configuration (LLM)
    groq_api_key: str
    
    # OpenAI Configuration (Text-to-Speech)
    openai_api_key: str
    openai_tts_voice: str = "alloy"  # Default voice (alloy, echo, fable, onyx, nova, shimmer)
    openai_tts_model: str = "tts-1"  # Default model (tts-1, tts-1-hd)
    # Default response format for OpenAI TTS. Can be set in .env as OPENAI_TTS_RESPONSE_FORMAT
    # Supported values: 'mp3' or 'pcm'
    openai_tts_response_format: str = "mp3"

    # ElevenLabs Configuration (Text-to-Speech)
    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Default voice ID (Adam)

    # Google Gemini Configuration (Multimodal AI)
    genai_api_key: str
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = 30
    ws_max_connections: int = 100
    
    # Audio Configuration
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 1024

    # Product Configuration
    product_name: str = "the 'Radiant Glow Skincare Set'"

    # Persona Configuration (JSON string of personas)
    personas_json: str = '[{"id": "friendly", "name": "Friendly Fiona", "description": "An enthusiastic and positive customer, easy to engage.", "avatar": "😊", "system_instruction": "You are Fiona, a friendly and enthusiastic customer. You are very interested in {product_name}. Ask positive questions about its benefits, ingredients, and how to use it. You are easy to convince and generally agreeable. Your tone should be cheerful and encouraging."}, {"id": "skeptical", "name": "Skeptical Sam", "description": "A cautious customer who questions claims and needs proof.", "avatar": "🤔", "system_instruction": "You are Sam, a skeptical and cautious customer. You are considering {product_name} but have many doubts. Question its effectiveness, compare it to other brands you\'ve \'heard of\', and challenge the salesperson\'s claims. You need solid facts and evidence to be persuaded. Your tone is questioning, not aggressive, but firm."}, {"id": "price-sensitive", "name": "Price-Sensitive Penny", "description": "A budget-conscious customer focused on value and cost.", "avatar": "💰", "system_instruction": "You are Penny, a budget-conscious customer. You like the sound of {product_name}, but you are very concerned about the price. Ask about discounts, payment plans, and whether it\'s truly worth the cost. Try to negotiate for a better deal. Emphasize value and affordability in your questions."}]'

    # System prompt for all personas
    system_prompt: str = "You are a helpful and concise AI sales training agent. Keep responses short and relevant. Follow all safety and privacy guidelines."
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    

SYSTEM_PROMPT = Settings().system_prompt


@lru_cache()
def get_settings() -> Settings:
    return Settings()
