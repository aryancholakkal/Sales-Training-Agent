const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export interface Persona {
  id: string;
  name: string;
  description: string;
  avatar: string;
  system_instruction: string;
}

export interface PersonaResponse {
  personas: Persona[];
}

export interface TranscriptMessage {
  id: number;
  speaker: 'Trainee' | 'Customer';
  text: string;
}

export type AgentStatus = 'idle' | 'connecting' | 'listening' | 'speaking' | 'error';

export class ApiService {
  static async getPersonas(): Promise<Persona[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/personas/`);
      if (!response.ok) {
        throw new Error(`Failed to fetch personas: ${response.statusText}`);
      }
      const data: PersonaResponse = await response.json();
      return data.personas;
    } catch (error) {
      console.error('Error fetching personas:', error);
      throw error;
    }
  }

  static async getPersona(personaId: string): Promise<Persona> {
    try {
      const response = await fetch(`${API_BASE_URL}/personas/${personaId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch persona: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching persona:', error);
      throw error;
    }
  }
}