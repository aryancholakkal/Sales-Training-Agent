
export interface Persona {
  id: string;
  name: string;
  description: string;
  avatar: string;
  systemInstruction: string;
}

export type AgentStatus = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error';

export interface Transcript {
  id: number;
  speaker: 'Trainee' | 'Customer';
  text: string;
}
