import { AgentStatus, TranscriptMessage } from './api';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/api/ws';

export interface WebSocketMessage {
  type: 'audio' | 'transcript' | 'status' | 'error' | 'end_session' | 'session_initialized' | 'pong' | 'transcript_history' | 'conversation_reset';
  data?: any;
}

export interface AudioMessage {
  audio: string; // base64 encoded
  mime_type: string;
  sample_rate?: number;
  channels?: number;
  bit_rate?: number;
  codec?: string;
  bit_depth?: number;
  encoding?: string;
  speaker?: string; // 'AI Assistant' or 'Customer'
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private personaId: string | null = null;
  private onStatusChange?: (status: AgentStatus) => void;
  private onTranscript?: (transcript: TranscriptMessage) => void;
  private onAudio?: (audioData: string, mimeType?: string, sampleRate?: number, channels?: number, bitRate?: number, codec?: string, bitDepth?: number, encoding?: string, speaker?: string) => void;
  private onError?: (error: string) => void;

  constructor(
    onStatusChange?: (status: AgentStatus) => void,
    onTranscript?: (transcript: TranscriptMessage) => void,
  onAudio?: (audioData: string, mimeType?: string, sampleRate?: number, channels?: number, bitRate?: number, codec?: string, bitDepth?: number, encoding?: string, speaker?: string) => void,
    onError?: (error: string) => void
  ) {
    this.onStatusChange = onStatusChange;
    this.onTranscript = onTranscript;
    this.onAudio = onAudio;
    this.onError = onError;
  }

  connect(personaId: string): Promise<boolean> {
    return new Promise((resolve, reject) => {
      try {
        this.personaId = personaId;
        this.ws = new WebSocket(`${WS_BASE_URL}/session/${personaId}`);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          resolve(true);
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          if (this.onError) {
            this.onError('WebSocket connection error');
          }
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket closed:', event.code, event.reason);
          if (this.onStatusChange) {
            this.onStatusChange('idle');
          }
        };

      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        reject(error);
      }
    });
  }

  private handleMessage(message: WebSocketMessage) {
    switch (message.type) {
      case 'session_initialized':
        console.log('Session initialized:', message.data);
        // Handle session initialization (optional callback)
        break;

      case 'status':
        if (this.onStatusChange && message.data?.status) {
          this.onStatusChange(message.data.status);
        }
        break;

      case 'transcript':
        if (this.onTranscript && message.data) {
          this.onTranscript(message.data);
        }
        break;

      case 'audio':
        if (this.onAudio && message.data?.audio) {
          this.onAudio(
            message.data.audio,
            message.data.mime_type,
            message.data.sample_rate,
            message.data.channels,
            message.data.bit_rate,
            message.data.codec,
            message.data.bit_depth,
            message.data.encoding,
            message.data.speaker
          );
        }
        break;

      case 'error':
        if (this.onError && message.data?.message) {
          this.onError(message.data.message);
        }
        break;

      case 'pong':
        // Handle pong response for ping keepalive
        console.debug('Received pong');
        break;

      case 'transcript_history':
        // Handle transcript history request response
        console.log('Transcript history:', message.data);
        break;

      case 'conversation_reset':
        // Handle conversation reset confirmation
        console.log('Conversation reset:', message.data);
        break;

      default:
        console.warn('Unknown message type:', message.type);
    }
  }

  sendAudio(audioData: string, mimeType: string = 'audio/pcm;rate=16000') {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type: 'audio',
        data: {
          audio: audioData,
          mime_type: mimeType
        }
      };
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  endSession() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type: 'end_session'
      };
      this.ws.send(JSON.stringify(message));
    }
    this.disconnect();
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.personaId = null;
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}