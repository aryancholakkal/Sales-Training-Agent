from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class SessionRequest(BaseModel):
    persona_id: str


class SessionResponse(BaseModel):
    session_id: str
    status: AgentStatus


class TranscriptMessage(BaseModel):
    id: int
    speaker: Literal["Trainee", "Customer"]
    text: str


class AudioData(BaseModel):
    data: str  # base64 encoded audio
    mime_type: str


class WebSocketMessage(BaseModel):
    type: Literal["audio", "transcript", "status", "error"]
    data: Optional[dict] = None