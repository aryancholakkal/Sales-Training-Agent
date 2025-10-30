# Sales Training Agent - Backend Migration Guide

## Overview

This guide documents the migration from Google Gemini API to a comprehensive real-time conversation system using:

- **WebRTC/Real-time**: LiveKit Agents framework for low-latency sessions and turn-taking
- **Speech-to-Text (STT)**: AssemblyAI using free $50 credits  
- **LLM**: Groq API keys for fast inference
- **Text-to-Speech (TTS)**: ElevenLabs free 10k monthly credits
- **Orchestration**: LiveKit session with VAD/turn detection for natural conversations

## What Changed

### Removed
- `google-generativeai` dependency
- `GenAIService` (replaced with modular services)
- Gemini API configuration

### Added
- **GroqService**: Fast LLM inference with Llama models
- **AssemblyAIService**: Real-time speech-to-text transcription
- **ElevenLabsService**: High-quality text-to-speech synthesis
- **LiveKitOrchestrationService**: Real-time WebRTC orchestration with VAD
- **Enhanced AudioService**: Multi-format audio processing and LiveKit integration

## New Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   WebSocket      │    │   LiveKit       │
│   (WebRTC)      │◄──►│   Gateway        │◄──►│   Orchestration │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        ▼
                         ┌──────▼──────┐    ┌─────────────────────┐
                         │  Audio      │    │  AI Services        │
                         │  Service    │    │  ┌─────────────────┐│
                         └─────────────┘    │  │ GroqService     ││
                                           │  │ (LLM)           ││
                                           │  ├─────────────────┤│
                                           │  │ AssemblyAI      ││
                                           │  │ (STT)           ││
                                           │  ├─────────────────┤│
                                           │  │ ElevenLabs      ││
                                           │  │ (TTS)           ││
                                           │  └─────────────────┘│
                                           └─────────────────────┘
```

## API Keys Setup

### 1. LiveKit
1. Sign up at [LiveKit Cloud](https://livekit.io/)
2. Create a new project
3. Get your API Key, API Secret, and WebSocket URL
4. Add to `.env`:
   ```
   LIVEKIT_API_KEY=your_api_key_here
   LIVEKIT_API_SECRET=your_api_secret_here
   LIVEKIT_WS_URL=wss://your-project.livekit.cloud
   ```

### 2. AssemblyAI ($50 free credits)
1. Sign up at [AssemblyAI](https://www.assemblyai.com/)
2. Get $50 in free credits automatically
3. Get your API key from the dashboard
4. Add to `.env`:
   ```
   ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
   ```

### 3. Groq (Free tier available)
1. Sign up at [Groq Console](https://console.groq.com/)
2. Create a new API key
3. Add to `.env`:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

### 4. ElevenLabs (10k free monthly credits)
1. Sign up at [ElevenLabs](https://elevenlabs.io/)
2. Get 10,000 characters free per month
3. Get your API key and optionally select a voice ID
4. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB  # Default: Adam voice
   ```

## Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Install Dependencies

**Note**: There are version compatibility requirements between LiveKit packages.

```bash
cd backend
# Using pip
pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

**If you encounter dependency conflicts**, install packages individually:
```bash
# Core dependencies first
pip install fastapi uvicorn websockets python-multipart python-dotenv pydantic pydantic-settings httpx python-jose passlib numpy

# AI services (compatible versions)
pip install "livekit>=0.12.0,<0.13.0" "livekit-agents==0.8.0"
pip install assemblyai==0.33.0
pip install groq==0.10.0
pip install elevenlabs==1.8.0
```

### Environment Configuration
Copy the example environment file and configure your API keys:
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Full `.env` Configuration
```env
# FastAPI Configuration
APP_NAME=AI Sales Training Backend
VERSION=1.0.0
DEBUG=False
HOST=0.0.0.0
PORT=8000

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]

# AI Services Configuration
# LiveKit Configuration (WebRTC/Real-time orchestration)
LIVEKIT_API_KEY=your_livekit_api_key_here
LIVEKIT_API_SECRET=your_livekit_api_secret_here
LIVEKIT_WS_URL=wss://your-livekit-instance.livekit.cloud

# AssemblyAI Configuration (Speech-to-Text)
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here

# Groq Configuration (LLM)
GROQ_API_KEY=your_groq_api_key_here

# ElevenLabs Configuration (Text-to-Speech)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB  # Default voice ID (Adam)

# WebSocket Configuration
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=100

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_CHUNK_SIZE=1024
```

## API Changes

### WebSocket Endpoint: `/ws/session/{persona_id}`

#### New Message Types

**Audio Input:**
```json
{
  "type": "audio",
  "data": {
    "audio": "base64_encoded_audio_data"
  }
}
```

**Text Input:**
```json
{
  "type": "text", 
  "data": {
    "text": "Hello, I want to learn about sales"
  }
}
```

**LiveKit Token Request:**
```json
{
  "type": "livekit_token_request",
  "data": {}
}
```

**Reset Conversation:**
```json
{
  "type": "reset_conversation",
  "data": {}
}
```

#### New Response Types

**Session Initialized:**
```json
{
  "type": "session_initialized",
  "data": {
    "session_id": "uuid",
    "room_name": "sales_training_uuid", 
    "status": "listening",
    "persona": "Sales Coach"
  }
}
```

**Enhanced Transcript:**
```json
{
  "type": "transcript",
  "data": {
    "id": 1,
    "speaker": "Trainee",
    "text": "I want to learn about sales",
    "is_final": true,
    "confidence": 0.95
  }
}
```

**Audio Response:**
```json
{
  "type": "audio",
  "data": {
    "audio": "base64_encoded_audio",
    "mime_type": "audio/mpeg"
  }
}
```

### New REST Endpoints

- `GET /api/sessions/active` - Get active session count
- `GET /api/sessions/{session_id}/transcripts` - Get session transcripts
- `POST /api/sessions/{session_id}/message` - Send message to session
- `GET /api/health` - Service health check

## Service Configuration

### GroqService
- Model: `llama3-8b-8192`
- Temperature: 0.8
- Max tokens: 1024
- Supports streaming responses

### AssemblyAI STT
- Real-time transcription
- Word boosting for sales terms
- Confidence scoring
- Partial and final transcripts

### ElevenLabs TTS
- High-quality voice synthesis
- Configurable voice settings
- Streaming audio generation
- Voice cloning support

### LiveKit Orchestration
- Real-time WebRTC rooms
- Voice Activity Detection (VAD)
- Turn-taking management
- Low-latency audio streaming

## Migration Checklist

- [x] Update environment variables
- [x] Install new dependencies  
- [x] Replace GenAI service with Groq
- [x] Implement AssemblyAI STT service
- [x] Implement ElevenLabs TTS service
- [x] Create LiveKit orchestration service
- [x] Update WebSocket handlers
- [x] Enhance audio processing
- [ ] Test real-time functionality
- [ ] Configure LiveKit rooms
- [ ] Optimize audio pipeline

## Testing

### Start the Backend
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Test WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session/default_persona');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

// Send text message
ws.send(JSON.stringify({
    type: 'text',
    data: { text: 'Hello, I want to learn about sales techniques' }
}));
```

## Performance Considerations

### Latency Optimization
- **Groq**: ~100-200ms inference time
- **AssemblyAI**: Real-time streaming STT
- **ElevenLabs**: ~500ms-1s for TTS generation
- **LiveKit**: <100ms WebRTC latency

### Cost Management
- **AssemblyAI**: $50 free credits (~8-10 hours of audio)
- **Groq**: Free tier with rate limits
- **ElevenLabs**: 10k characters/month free
- **LiveKit**: Free tier available

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **API Key Issues**: Verify all API keys are correctly set
3. **Audio Format Issues**: Ensure 16kHz, 16-bit, mono PCM format
4. **WebSocket Disconnections**: Check network stability and error handling

### Debug Mode
Set `DEBUG=True` in `.env` for detailed logging.

### Logs
Monitor logs for service-specific errors:
```bash
tail -f logs/app.log
```

## Future Enhancements

1. **WebRTC Integration**: Direct browser-to-LiveKit WebRTC streaming
2. **Voice Activity Detection**: Improved turn-taking with VAD thresholds
3. **Multi-language Support**: Configure AssemblyAI for different languages
4. **Voice Cloning**: Custom voice training with ElevenLabs
5. **Analytics**: Conversation analysis and performance metrics

## Support

For issues with the migration:
1. Check the logs for specific error messages
2. Verify API key configuration
3. Test individual services independently
4. Check network connectivity to all APIs

## Credits

This migration leverages the following services:
- [LiveKit](https://livekit.io/) - Real-time communications
- [AssemblyAI](https://www.assemblyai.com/) - Speech-to-Text
- [Groq](https://groq.com/) - LLM inference  
- [ElevenLabs](https://elevenlabs.io/) - Text-to-Speech