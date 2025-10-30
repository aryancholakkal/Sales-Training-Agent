import json
import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Optional
from ...services.persona_service import PersonaService
from ...services.livekit_service import LiveKitOrchestrationService
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
    orchestration_service = None
    
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
        
        # Get settings
        settings = get_settings()
        
        # Initialize LiveKit orchestration service
        orchestration_service = LiveKitOrchestrationService(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_ws_url
        )
        
        # Store session info
        active_sessions[session_id] = {
            "websocket": websocket,
            "persona": persona,
            "orchestration_service": orchestration_service,
            "transcripts": [],
            "room_name": f"sales_training_{session_id}"
        }
        
        # Callback functions for orchestration service
        async def on_status_change(status: AgentStatus):
            await websocket.send_text(json.dumps({
                "type": "status",
                "data": {"status": status.value}
            }))
        
        async def on_message_received(message):
            """Handle messages from the orchestration service"""
            try:
                session_data = active_sessions.get(session_id)
                if not session_data:
                    return
                
                # Handle different types of messages
                if isinstance(message, dict):
                    if message.get("type") == "audio":
                        # Audio response from TTS
                        await websocket.send_text(json.dumps({
                            "type": "audio",
                            "data": {
                                "audio": message.get("data"),
                                "mime_type": message.get("mime_type", "audio/mpeg")
                            }
                        }))
                    else:
                        # Generic message
                        await websocket.send_text(json.dumps({
                            "type": "message",
                            "data": {"message": str(message)}
                        }))
                else:
                    # Text message from LLM
                    await websocket.send_text(json.dumps({
                        "type": "message", 
                        "data": {"message": str(message)}
                    }))
                    
            except Exception as e:
                logger.error(f"Error handling orchestration message: {e}")
        
        async def on_transcript_received(transcript_data):
            """Handle transcript updates from STT/TTS"""
            try:
                session_data = active_sessions.get(session_id)
                if not session_data:
                    return
                
                # Create transcript message
                transcript = TranscriptMessage(
                    id=len(session_data['transcripts']),
                    speaker=transcript_data.get("speaker", "Unknown"),
                    text=transcript_data.get("text", "")
                )
                
                # Only add final transcripts to history
                if transcript_data.get("is_final", True):
                    session_data['transcripts'].append(transcript)
                
                # Send transcript update
                await websocket.send_text(json.dumps({
                    "type": "transcript",
                    "data": {
                        **transcript.dict(),
                        "is_final": transcript_data.get("is_final", True),
                        "confidence": transcript_data.get("confidence")
                    }
                }))
                
            except Exception as e:
                logger.error(f"Error handling transcript: {e}")
        
        # Initialize orchestration session
        room_name = active_sessions[session_id]["room_name"]
        success = await orchestration_service.initialize_session(
            room_name=room_name,
            persona_instruction=persona.system_instruction,
            groq_api_key=settings.groq_api_key,
            assemblyai_api_key=settings.assemblyai_api_key,
            elevenlabs_api_key=settings.elevenlabs_api_key,
            elevenlabs_voice_id=settings.elevenlabs_voice_id,
            on_message_callback=on_message_received,
            on_status_callback=on_status_change,
            on_transcript_callback=on_transcript_received
        )
        
        if not success:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Failed to create AI orchestration session"}
            }))
            await websocket.close()
            return
        
        # Send initial status and room info
        await websocket.send_text(json.dumps({
            "type": "session_initialized",
            "data": {
                "session_id": session_id,
                "room_name": room_name,
                "status": orchestration_service.get_status().value,
                "persona": persona.name
            }
        }))
        
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "status",
            "data": {"status": orchestration_service.get_status().value}
        }))
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "audio":
                    # Handle audio input for STT processing
                    audio_data = message_data.get("data", {}).get("audio", "")
                    if audio_data:
                        # For now, we'll decode base64 and send to the orchestration service
                        # The orchestration service will handle STT processing
                        try:
                            # Send audio to LiveKit orchestration (this will be processed by AssemblyAI STT)
                            # In a real LiveKit implementation, audio would be streamed through WebRTC
                            # For now, we can process it through our STT service directly
                            if orchestration_service.stt_service:
                                await orchestration_service.stt_service.send_audio_base64(audio_data)
                        except Exception as e:
                            logger.error(f"Error processing audio: {e}")
                
                elif message_type == "text":
                    # Handle direct text input
                    text_message = message_data.get("data", {}).get("text", "")
                    if text_message:
                        await orchestration_service.send_text_message(text_message)
                
                elif message_type == "livekit_token_request":
                    # Handle LiveKit token request for WebRTC connection
                    # This would be used for direct WebRTC audio streaming
                    await websocket.send_text(json.dumps({
                        "type": "livekit_token",
                        "data": {
                            "token": "placeholder_token",  # In real implementation, generate actual LiveKit token
                            "room_name": room_name,
                            "ws_url": settings.livekit_ws_url
                        }
                    }))
                
                elif message_type == "ping":
                    # Handle ping for connection keepalive
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {"timestamp": message_data.get("data", {}).get("timestamp")}
                    }))
                
                elif message_type == "get_transcripts":
                    # Send current transcript history
                    session_data = active_sessions.get(session_id)
                    if session_data:
                        transcripts = [t.dict() for t in session_data['transcripts']]
                        await websocket.send_text(json.dumps({
                            "type": "transcript_history",
                            "data": {"transcripts": transcripts}
                        }))
                
                elif message_type == "reset_conversation":
                    # Reset the conversation
                    if orchestration_service.groq_service:
                        await orchestration_service.groq_service.reset_conversation()
                    
                    # Clear transcripts
                    session_data = active_sessions.get(session_id)
                    if session_data:
                        session_data['transcripts'].clear()
                    
                    await websocket.send_text(json.dumps({
                        "type": "conversation_reset",
                        "data": {"message": "Conversation has been reset"}
                    }))
                
                elif message_type == "end_session":
                    break
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
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
                    "data": {"message": f"Internal server error: {str(e)}"}
                }))
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": f"Connection error: {str(e)}"}
        }))
    finally:
        # Cleanup
        if orchestration_service:
            await orchestration_service.close_session()
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


@router.get("/sessions/{session_id}/transcripts")
async def get_session_transcripts(session_id: str):
    """Get transcripts for a specific session"""
    session_data = active_sessions.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    transcripts = [t.dict() for t in session_data['transcripts']]
    return {"transcripts": transcripts}


@router.post("/sessions/{session_id}/message")
async def send_message_to_session(session_id: str, message: dict):
    """Send a message to a specific session"""
    session_data = active_sessions.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    orchestration_service = session_data.get("orchestration_service")
    if not orchestration_service:
        raise HTTPException(status_code=500, detail="Orchestration service not available")
    
    text = message.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text message is required")
    
    success = await orchestration_service.send_text_message(text)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send message")
    
    return {"status": "message_sent", "text": text}


@router.get("/health")
async def health_check():
    """Health check endpoint for WebSocket service"""
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "services": {
            "websocket": "operational",
            "livekit_orchestration": "available"
        }
    }