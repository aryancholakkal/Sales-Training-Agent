import json
import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Optional
from ...services.persona_service import PersonaService
from ...services.genai_service import GenAIService
from ...models.session import AgentStatus, WebSocketMessage, TranscriptMessage
from ...core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Store active sessions
active_sessions: Dict[str, Dict] = {}


@router.websocket("/session/{persona_id}")
async def websocket_endpoint(websocket: WebSocket, persona_id: str):
    await websocket.accept()
    
    session_id = str(uuid.uuid4())
    genai_service = None
    
    try:
        # Get persona
        persona = PersonaService.get_persona_by_id(persona_id)
        if not persona:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Persona not found"}
            }))
            await websocket.close()
            return
        
        # Initialize GenAI service
        settings = get_settings()
        genai_service = GenAIService(settings.gemini_api_key)
        
        # Store session info
        active_sessions[session_id] = {
            "websocket": websocket,
            "persona": persona,
            "genai_service": genai_service,
            "transcripts": []
        }
        
        # Callback functions for GenAI service
        async def on_status_change(status: AgentStatus):
            await websocket.send_text(json.dumps({
                "type": "status",
                "data": {"status": status.value}
            }))
        
        async def on_genai_message(message):
            try:
                session_data = active_sessions.get(session_id)
                if not session_data:
                    return
                
                # Handle transcription
                if hasattr(message, 'server_content'):
                    server_content = message.server_content
                    
                    # Input transcription (user speech)
                    if server_content.get('input_transcription'):
                        text = server_content['input_transcription'].get('text', '')
                        if text:
                            transcript = TranscriptMessage(
                                id=len(session_data['transcripts']),
                                speaker="Trainee",
                                text=text
                            )
                            session_data['transcripts'].append(transcript)
                            await websocket.send_text(json.dumps({
                                "type": "transcript",
                                "data": transcript.dict()
                            }))
                    
                    # Output transcription (AI speech)
                    if server_content.get('output_transcription'):
                        text = server_content['output_transcription'].get('text', '')
                        if text:
                            transcript = TranscriptMessage(
                                id=len(session_data['transcripts']),
                                speaker="Customer",
                                text=text
                            )
                            session_data['transcripts'].append(transcript)
                            await websocket.send_text(json.dumps({
                                "type": "transcript",
                                "data": transcript.dict()
                            }))
                    
                    # Audio response
                    if server_content.get('model_turn'):
                        parts = server_content['model_turn'].get('parts', [])
                        for part in parts:
                            if part.get('inline_data') and part['inline_data'].get('data'):
                                audio_data = part['inline_data']['data']
                                await websocket.send_text(json.dumps({
                                    "type": "audio",
                                    "data": {
                                        "audio": audio_data,
                                        "mime_type": "audio/pcm"
                                    }
                                }))
                                
            except Exception as e:
                logger.error(f"Error handling GenAI message: {e}")
        
        # Create GenAI session
        success = await genai_service.create_session(
            persona.system_instruction,
            on_genai_message,
            on_status_change
        )
        
        if not success:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Failed to create AI session"}
            }))
            await websocket.close()
            return
        
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "status",
            "data": {"status": genai_service.get_status().value}
        }))
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "audio":
                    # Forward audio to GenAI
                    audio_data = message_data.get("data", {}).get("audio", "")
                    if audio_data:
                        await genai_service.send_audio(audio_data)
                        
                elif message_data.get("type") == "end_session":
                    break
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Internal server error"}
                }))
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": "Connection error"}
        }))
    finally:
        # Cleanup
        if genai_service:
            await genai_service.close_session()
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        try:
            await websocket.close()
        except:
            pass


@router.get("/sessions/active")
async def get_active_sessions():
    """Get count of active sessions"""
    return {"active_sessions": len(active_sessions)}