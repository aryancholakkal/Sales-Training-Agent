# AI Sales Training Simulator

An AI-powered voice agent application for training sales representatives through realistic customer interactions. The application features a React frontend and FastAPI backend architecture with real-time audio processing using Google's Gemini AI.

## Architecture Overview

```
.
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── services/      # API and WebSocket services
│   │   ├── types/         # TypeScript type definitions
│   │   └── utils/         # Utility functions
│   ├── package.json
│   └── vite.config.ts
├── backend/               # FastAPI Python backend
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Configuration
│   │   ├── models/        # Pydantic models
│   │   ├── services/      # Business logic
│   │   └── main.py        # FastAPI app
│   ├── requirements.txt
│   └── .env
└── README.md
```

## Features

- **Real-time Voice Interaction**: Direct voice communication with AI personas
- **Multiple Customer Personas**: Practice with different customer types (Friendly, Skeptical, Price-Sensitive)
- **Live Transcription**: Real-time speech-to-text for both trainee and AI responses
- **WebSocket Communication**: Low-latency real-time communication between frontend and backend
- **Modular Architecture**: Separated frontend and backend for scalability

## Prerequisites

- **Backend**: Python 3.8+, pip
- **Frontend**: Node.js 16+, npm
- **API Key**: Google Gemini API key

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-sales-training-simulator
```

### 2. Backend Setup

#### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Environment Configuration
Create or update `backend/.env`:
```env
# FastAPI Configuration
APP_NAME=AI Sales Training Backend
VERSION=1.0.0
DEBUG=False
HOST=0.0.0.0
PORT=8000

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]

# GenAI Configuration
GEMINI_API_KEY=your_actual_gemini_api_key_here

# WebSocket Configuration
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=100
```

**Important**: Replace `your_actual_gemini_api_key_here` with your actual Google Gemini API key.

#### Start the Backend Server
```bash
# From the backend directory
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

#### Install Dependencies
```bash
cd frontend
npm install
```

#### Environment Configuration
Create or update `frontend/.env`:
```env
# Backend API Configuration
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000/api/ws
```

#### Start the Frontend Development Server
```bash
# From the frontend directory
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Running the Application

### Development Mode

1. **Start the Backend** (Terminal 1):
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start the Frontend** (Terminal 2):
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the Application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Production Build

#### Backend
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm run build
npm run preview
```

## API Documentation

### REST Endpoints

- `GET /api/personas/` - Get all available personas
- `GET /api/personas/{persona_id}` - Get specific persona
- `GET /api/health` - Health check
- `GET /api/ws/sessions/active` - Get active WebSocket sessions

### WebSocket Endpoint

- `WS /api/ws/session/{persona_id}` - Start training session with specific persona

### Message Types

#### Incoming (Frontend → Backend)
```json
{
  "type": "audio",
  "data": {
    "audio": "base64_encoded_audio",
    "mime_type": "audio/pcm;rate=16000"
  }
}
```

#### Outgoing (Backend → Frontend)
```json
{
  "type": "status|transcript|audio|error",
  "data": {
    // Type-specific payload
  }
}
```

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure both frontend and backend URLs are correctly configured in environment variables.

2. **WebSocket Connection Failed**: 
   - Verify backend is running on port 8000
   - Check firewall settings
   - Ensure WebSocket URL in frontend .env is correct

3. **Audio Permissions Denied**:
   - Allow microphone access in browser
   - Use HTTPS in production for microphone access

4. **API Key Issues**:
   - Verify Gemini API key is valid and has sufficient quota
   - Check API key is correctly set in backend/.env

5. **Module Not Found Errors**:
   - Backend: Ensure all Python dependencies are installed (`pip install -r requirements.txt`)
   - Frontend: Ensure all Node dependencies are installed (`npm install`)

### Development Tips

- Use browser developer tools to monitor WebSocket connections
- Check backend logs for API errors
- Verify microphone permissions in browser settings
- Test API endpoints directly at http://localhost:8000/docs

## Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS
- **Backend**: FastAPI, Python 3.8+, WebSockets, Pydantic
- **AI**: Google Gemini 2.0 Flash with Live API
- **Real-time**: WebSocket communication for audio streaming
- **Build Tools**: Vite (frontend), Uvicorn (backend)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test both frontend and backend
5. Submit a pull request

## License

This project is licensed under the MIT License.
