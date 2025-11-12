import asyncio
import json
import uuid
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Optional
from ...services.persona_service import PersonaService, get_persona_prompt
from ...services.livekit_service import LiveKitOrchestrationService
from ...models.session import AgentStatus, WebSocketMessage, TranscriptMessage
from ...core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Store active sessions
active_sessions: Dict[str, Dict] = {}


async def safe_send_message(websocket: WebSocket, data: dict) -> bool:
    """Safely send a message through WebSocket with connection state check"""
    try:
        if websocket.client_state.name == "CONNECTED":
            await websocket.send_text(json.dumps(data))
            return True
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")
    return False


@router.websocket("/session/{persona_id}")
async def websocket_endpoint(websocket: WebSocket, persona_id: str):
    await websocket.accept()

    session_id = str(uuid.uuid4())
    orchestration_service = None

    # Track connection state
    is_connected = True
    background_tasks = set()

    # Throttling for repetitive audio/status logs (per-session)
    last_audio_log_time = 0.0
    audio_log_interval = 1.0  # seconds between verbose logs
    last_stt_error_time = 0.0
    stt_error_interval = 2.0  # seconds between repeated STT error logs
    audio_frames_sent = 0  # count frames for periodic summaries
    # Manual listening state
    # Create a cancellation event for graceful shutdown
    cancel_event = asyncio.Event()
    
    # Get settings and log diagnostic information
    settings = get_settings()
    logger.info("=== Diagnostic Information ===")
    logger.info(f"Deepgram API Key present: {bool(settings.deepgram_api_key)}")
    logger.info(f"Deepgram API Key length: {len(settings.deepgram_api_key) if settings.deepgram_api_key else 0}")
    logger.info(f"First 4 chars of Deepgram API Key: {settings.deepgram_api_key[:4] if settings.deepgram_api_key else 'N/A'}")
    
    try:
        # Get persona
        persona = PersonaService.get_persona_by_id(persona_id)
        if not persona:
            await safe_send_message(websocket, {
                "type": "error",
                "data": {"message": "Persona not found"}
            })
            await websocket.close()
            return
        
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
            "room_name": f"sales_training_{session_id}",
            "next_transcript_id": 0,
            "transcript_state": {
                "Trainee": {"id": None, "is_final": True},
                "Customer": {"id": None, "is_final": True}
            }
        }
        
        # Set up callbacks that check connection state
        async def safe_send(data):
            """Send data only if connection is still open"""
            if is_connected:
                await safe_send_message(websocket, data)

        # Callback functions for orchestration service
        async def on_status_change(status: AgentStatus):
            await safe_send({
                "type": "status",
                "data": {"status": status.value}
            })

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
                        await safe_send({
                            "type": "audio",
                            "data": {
                                "audio": message.get("data"),
                                "mime_type": message.get("mime_type", "audio/mpeg")
                            }
                        })
                    elif message.get("type") == "audio_stop":
                        await safe_send({
                            "type": "audio_stop",
                            "data": {
                                "reason": message.get("reason")
                            }
                        })
                    elif message.get("type") == "transcript":
                        # Streaming transcript from LLM
                        await safe_send({
                            "type": "transcript",
                            "data": {
                                "speaker": "Customer",
                                "text": message.get("text", ""),
                                "is_final": message.get("is_final", False),
                            }
                        })
                    else:
                        # Generic message
                        await safe_send({
                            "type": "message",
                            "data": {"message": str(message)}
                        })
                else:
                    # Text message from LLM (assume streaming)
                    await safe_send({
                        "type": "transcript",
                        "data": {
                            "speaker": "Customer",
                            "text": str(message),
                            "is_final": False,
                        }
                    })

            except Exception as e:
                logger.error(f"Error handling orchestration message: {e}")

        def merge_transcript_text(existing: str, incoming: str) -> str:
            if not existing:
                return incoming
            if not incoming:
                return existing
            if existing == incoming:
                return existing
            if incoming.startswith(existing):
                return incoming
            if existing.endswith(incoming):
                return existing

            max_overlap = min(len(existing), len(incoming))
            for k in range(max_overlap, 0, -1):
                if existing.endswith(incoming[:k]):
                    return existing + incoming[k:]
            return existing + incoming

        async def on_transcript_received(transcript_data):
            """Handle transcript updates from STT/TTS"""
            try:
                session_data = active_sessions.get(session_id)
                if not session_data:
                    logger.warning(f"[WebSocket] No session data found for session_id: {session_id}")
                    return

                logger.debug(f"[WebSocket] Received transcript data: {transcript_data}")

                # Map speaker labels to allowed values
                speaker_raw = transcript_data.get("speaker", "Unknown")
                if speaker_raw == "AI Assistant":
                    speaker = "Customer"
                elif speaker_raw in ["Trainee", "Customer"]:
                    speaker = speaker_raw
                else:
                    speaker = "Customer"  # Default fallback

                is_final = transcript_data.get("is_final", True)
                text = transcript_data.get("text", "")
                confidence = transcript_data.get("confidence")

                transcript_state = session_data.setdefault(
                    "transcript_state",
                    {
                        "Trainee": {"id": None, "is_final": True},
                        "Customer": {"id": None, "is_final": True}
                    }
                )

                speaker_state = transcript_state.get(speaker)
                if speaker_state is None:
                    speaker_state = {"id": None, "is_final": True}
                    transcript_state[speaker] = speaker_state

                current_id: Optional[int] = speaker_state.get("id")
                previous_was_final = speaker_state.get("is_final", True)

                if current_id is None or (previous_was_final and not is_final):
                    current_id = session_data.get("next_transcript_id", 0)
                    session_data["next_transcript_id"] = current_id + 1
                    speaker_state["id"] = current_id

                transcript_payload = {
                    "speaker": speaker,
                    "text": text,
                    "is_final": is_final,
                    "confidence": confidence,
                    "id": current_id
                }

                if is_final:
                    transcripts_list = session_data['transcripts']
                    existing_index = next((idx for idx, t in enumerate(transcripts_list) if t.id == current_id), None)
                    if existing_index is not None:
                        existing_transcript = transcripts_list[existing_index]
                        merged_text = merge_transcript_text(existing_transcript.text, text)
                        transcripts_list[existing_index] = TranscriptMessage(
                            id=current_id,
                            speaker=speaker,
                            text=merged_text,
                            is_final=True,
                            confidence=confidence
                        )
                    else:
                        transcripts_list.append(TranscriptMessage(
                            id=current_id,
                            speaker=speaker,
                            text=text,
                            is_final=True,
                            confidence=confidence
                        ))

                if is_final:
                    logger.info(f"[WebSocket] Added final transcript to history: '{text}' by {speaker} (id={current_id})")

                speaker_state["is_final"] = is_final

                logger.debug(f"[WebSocket] Sending transcript message to client: {transcript_payload}")
                await safe_send({
                    "type": "transcript",
                    "data": transcript_payload
                })

            except Exception as e:
                logger.error(f"Error handling transcript: {e}")
        
        # Initialize orchestration session
        room_name = active_sessions[session_id]["room_name"]
        combined_prompt = get_persona_prompt(persona)
        logger.info(f"Combined system prompt: {combined_prompt}")
        success = await orchestration_service.initialize_session(
            room_name=room_name,
            persona_instruction=combined_prompt,
            groq_api_key=settings.groq_api_key,
            deepgram_api_key=settings.deepgram_api_key,
            openai_api_key=settings.openai_api_key,
            openai_tts_voice=settings.openai_tts_voice,
            on_message_callback=on_message_received,
            on_status_callback=on_status_change,
            on_transcript_callback=on_transcript_received
        )
        
        if not success:
            await safe_send_message(websocket, {
                "type": "error",
                "data": {"message": "Failed to create AI orchestration session"}
            })
            await websocket.close()
            return
        
        # Send initial status and room info
        await safe_send_message(websocket, {
            "type": "session_initialized",
            "data": {
                "session_id": session_id,
                "room_name": room_name,
                "status": orchestration_service.get_status().value,
                "persona": persona.name
            }
        })
        
        # Send initial status
        await safe_send_message(websocket, {
            "type": "status",
            "data": {"status": orchestration_service.get_status().value}
        })
        
        # Listen for messages
        while True:
            try:
                # Check for cancellation signal
                if cancel_event.is_set():
                    logger.info("[WebSocket] Cancellation requested, breaking message loop")
                    break

                data = await websocket.receive_text()
                message_data = json.loads(data)

                message_type = message_data.get("type")

                if message_type == "audio":
                    # Handle audio input for STT processing
                    audio_data = message_data.get("data", {}).get("audio", "")
                    if not audio_data:
                        continue
                    now = time.time()
                    # Verbose per-audio logs throttled to avoid flooding logs
                    if now - last_audio_log_time >= audio_log_interval:
                        logger.info(f"[WebSocket] Received audio data: {len(audio_data)} base64 chars")
                        last_audio_log_time = now
                    else:
                        logger.debug(f"[WebSocket] Received audio (throttled): {len(audio_data)} base64 chars")
                    # Check orchestration service
                    if not orchestration_service:
                        if now - last_stt_error_time >= stt_error_interval:
                            logger.error("[WebSocket] Orchestration service is None")
                            last_stt_error_time = now
                        continue
                    # Check stt_service
                    if not hasattr(orchestration_service, 'stt_service') or orchestration_service.stt_service is None:
                        if now - last_stt_error_time >= stt_error_interval:
                            logger.error("[WebSocket] STT service not available in orchestration service")
                            last_stt_error_time = now
                        continue
                    try:
                        stt_is_connected = orchestration_service.stt_service.is_connected()
                        # Occasionally log full status to help debugging
                        if now - last_audio_log_time < 0.001:  # just-logged verbose block
                            logger.info("=== STT Service Status Check ===")
                            logger.info(f"[WebSocket] STT service state: Connected={stt_is_connected}, Status={orchestration_service.stt_service.get_status()}, IsRunning={orchestration_service.stt_service.is_running}")
                        if stt_is_connected:
                            # Count frames and log summary periodically
                            audio_frames_sent += 1
                            now = time.time()
                            if now - last_audio_log_time >= audio_log_interval:
                                logger.info(f"[WebSocket] Processed {audio_frames_sent} audio frames in last {audio_log_interval:.1f}s")
                                audio_frames_sent = 0
                                last_audio_log_time = now
                            else:
                                logger.debug("[WebSocket] Sending audio frame to STT")
                            task = asyncio.create_task(
                                orchestration_service.stt_service.send_audio_base64(audio_data)
                            )
                            background_tasks.add(task)
                            task.add_done_callback(background_tasks.discard)
                            # Check cancellation after creating task
                            if cancel_event.is_set():
                                logger.info("[WebSocket] Cancellation requested during audio processing")
                                break
                    except Exception as e:
                        logger.error(f"Error processing audio: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                    # Do not disable listening after each audio frame; remain in listening state until user action

                elif message_type == "text":
                    # Handle direct text input
                    text_message = message_data.get("data", {}).get("text", "")
                    if text_message:
                        task = asyncio.create_task(
                            orchestration_service.send_text_message(text_message)
                        )
                        background_tasks.add(task)
                        task.add_done_callback(background_tasks.discard)

                elif message_type == "livekit_token_request":
                    # Handle LiveKit token request for WebRTC connection
                    await safe_send({
                        "type": "livekit_token",
                        "data": {
                            "token": "placeholder_token",
                            "room_name": room_name,
                            "ws_url": settings.livekit_ws_url
                        }
                    })

                elif message_type == "ping":
                    # Handle ping for connection keepalive
                    await safe_send({
                        "type": "pong",
                        "data": {"timestamp": message_data.get("data", {}).get("timestamp")}
                    })

                elif message_type == "get_transcripts":
                    # Send current transcript history
                    session_data = active_sessions.get(session_id)
                    if session_data:
                        transcripts = [t.dict() for t in session_data['transcripts']]
                        await safe_send({
                            "type": "transcript_history",
                            "data": {"transcripts": transcripts}
                        })

                elif message_type == "reset_conversation":
                    # Reset the conversation
                    if orchestration_service.groq_service:
                        task = asyncio.create_task(
                            orchestration_service.groq_service.reset_conversation()
                        )
                        background_tasks.add(task)
                        task.add_done_callback(background_tasks.discard)

                    # Clear transcripts
                    session_data = active_sessions.get(session_id)
                    if session_data:
                        session_data['transcripts'].clear()
                        session_data['next_transcript_id'] = 0
                        session_data['transcript_state'] = {
                            "Trainee": {"id": None, "is_final": True},
                            "Customer": {"id": None, "is_final": True}
                        }
                        try:
                            orchestration_service.reset_turn_state()
                        except Exception as e:
                            logger.error(f"Error resetting turn state: {e}")

                    await safe_send({
                        "type": "conversation_reset",
                        "data": {"message": "Conversation has been reset"}
                    })

                elif message_type == "end_session":
                    break

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except WebSocketDisconnect:
                logger.info("[WebSocket] Client disconnected")
                break
            except json.JSONDecodeError:
                await safe_send({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await safe_send({
                    "type": "error",
                    "data": {"message": f"Internal server error: {str(e)}"}
                })
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await safe_send_message(websocket, {
            "type": "error",
            "data": {"message": f"Connection error: {str(e)}"}
        })
    finally:
        # Mark connection as closed and set cancellation event
        is_connected = False
        cancel_event.set()

        logger.info("Starting service cleanup...")

        # Cancel all background tasks
        for task in background_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        # Clean up orchestration service
        try:
            if orchestration_service:
                await orchestration_service.close_session()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        if session_id in active_sessions:
            del active_sessions[session_id]

        try:
            await websocket.close()
        except:
            pass

        logger.info("Cleanup completed")


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