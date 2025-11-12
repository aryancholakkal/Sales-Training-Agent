# AI Sales Training Agent

Interactive voice simulations for sales reps, powered by real-time STT, LLM, and TTS services. The system pairs a FastAPI backend with a React frontend to orchestrate trainee/customer conversations, live transcripts, scoring, and post-call evaluation reports.

## Architecture Overview

```
.
├── frontend/              # React + TypeScript SPA
│   ├── src/
│   │   ├── components/    # UI widgets (evaluation report, controls)
│   │   ├── services/      # REST + WebSocket clients
│   │   ├── types/         # Shared TypeScript models
│   │   └── utils/         # Audio helpers (streaming, resampling)
│   ├── package.json
│   └── vite.config.ts
├── backend/               # FastAPI service layer
│   ├── app/
│   │   ├── api/           # REST + WS endpoints
│   │   ├── core/          # Settings, config
│   │   ├── models/        # Pydantic schemas (sessions, evaluation)
│   │   ├── services/      # Groq, Deepgram, OpenAI TTS, LiveKit orchestration
│   │   └── main.py        # FastAPI application instance
│   ├── requirements.txt
│   └── .env               # Environment variables (not committed)
└── README.md
```

## Capabilities

- Real-time two-way voice simulation with LiveKit, Groq LLM responses, Deepgram STT, and OpenAI TTS playback
- Persona-driven customer behaviour with configurable prompts and avatars
- Pause-aware turn taking that delays AI replies until the trainee truly finishes speaking
- Post-call evaluation pipeline scoring core sales skills and producing shareable summaries
- Web dashboard showing transcripts, status events, and audio playback in near real time
- Configurable service parameters (Deepgram stream options, user pause tolerance, TTS voice/model)

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pydantic, Pydantic Settings, asyncio
- **Real-time & AI Services**: LiveKit Python SDK, Groq LLM API, Deepgram Streaming STT, OpenAI Text-to-Speech, optional Gemini/ElevenLabs adapters
- **Frontend**: React 19, TypeScript, Vite 6, Tailwind CSS
- **Tooling**: WebSockets, NumPy (audio utils), PostCSS, ESLint (via TypeScript tooling)

## Prerequisites

- Python 3.10 or newer
- Node.js 18+ with npm
- API credentials:
   - `GROQ_API_KEY` (required)
   - `DEEPGRAM_API_KEY` (required)
   - `OPENAI_API_KEY` (required for TTS)
   - `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_WS_URL` (required for orchestration)
   - `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` (required if ElevenLabs fallback is used)
   - `GENAI_API_KEY` (required only when enabling Gemini flows)

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd Sales-Training-Agent
```

### 2. Backend

Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env` (sample below). Replace placeholder values with your own keys; optional settings can be omitted for defaults.

```env
# FastAPI
APP_NAME=AI Sales Training Backend
VERSION=1.0.0
DEBUG=false
HOST=0.0.0.0
PORT=8000

# CORS origins (JSON array string)
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]

# Core services
GROQ_API_KEY=your_groq_key
DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret
LIVEKIT_WS_URL=wss://<your-livekit-host>

# Optional/advanced
OPENAI_TTS_VOICE=alloy
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_RESPONSE_FORMAT=mp3
DEEPGRAM_STREAM_PARAMS={"filler_words":"false"}
USER_PAUSE_MS=1200

# Legacy/alternate providers (set if you enable these paths)
ELEVENLABS_API_KEY=dummy_or_real_if_used
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
GENAI_API_KEY=dummy_if_unused

# WebSocket thresholds
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=100
```

Launch the backend:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger docs live at `http://localhost:8000/docs`.

### 3. Frontend

Install dependencies:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000/api/ws
```

Start the dev server:

```bash
npm run dev
```

Visit `http://localhost:3000` to interact with the simulator.

## Running in Development

1. Start the backend (`uvicorn`) in one shell
2. Start the frontend (`npm run dev`) in another
3. Open the web app, pick a persona, and allow microphone access

Production builds use `npm run build && npm run preview` for the frontend and a non-reload `uvicorn` command (or ASGI host of choice) for the backend.

## Key Endpoints

- `GET /api/health` — backend health probe
- `GET /api/personas/` — list available customer personas
- `POST /api/evaluations/` — generate post-call evaluation summaries
- `WS /api/ws/session/{persona_id}` — primary LiveKit-driven conversation channel

Example evaluation request:

```json
POST /api/evaluations/
{
   "conversationId": "session-123",
   "transcript": [
      { "speaker": "Trainee", "text": "Hello!" },
      { "speaker": "Customer", "text": "Hi there." }
   ]
}
```

The API returns category scores, strengths, improvements, and an overall summary that the frontend renders post-session.

## Troubleshooting

- **AI responds too quickly**: Increase `USER_PAUSE_MS` or verify Deepgram latency; backend logs show when transcripts are dispatched.
- **No audio returned**: Confirm OpenAI TTS credentials and that your browser trusts the site for autoplay/audio playback.
- **WebSocket disconnects**: Ensure the backend `WS_MAX_CONNECTIONS` limit is not exceeded and LiveKit credentials are valid.
- **Microphone access denied**: Allow microphone usage in your browser; HTTPS is required in production.
- **Service API errors**: Inspect backend logs in `backend/logs/app.log.*` for provider responses.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Implement and document your changes
4. Run backend and frontend locally to verify
5. Open a pull request

## License

Distributed under the MIT License.
