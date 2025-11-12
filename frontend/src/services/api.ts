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

export interface Product {
  id: string;
  name: string;
  tagline?: string;
  description?: string;
  price?: string;
  key_benefits?: string[];
  usage_notes?: string;
}

export interface ProductResponse {
  products: Product[];
}

export interface TranscriptMessage {
  id?: number;
  speaker: 'Trainee' | 'Customer';
  text: string;
  is_final?: boolean;
  confidence?: number;
}

export type EvaluationCategoryName =
  | 'Grammar & Clarity'
  | 'Tone & Empathy'
  | 'Product Knowledge'
  | 'Response Strategy'
  | 'Sales Effectiveness';

export interface EvaluationCategoryFeedback {
  category: EvaluationCategoryName;
  score: number;
  comment: string;
}

export interface EvaluationResponse {
  report_id: string;
  persona_id: string;
  product_id?: string;
  created_at: string;
  overall_score: number;
  summary_feedback: string;
  detailed_feedback: EvaluationCategoryFeedback[];
}

export interface EvaluationRequest {
  persona_id: string;
  product_id?: string;
  transcript: TranscriptMessage[];
}

export type AgentStatus = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error';

export class ApiService {
  static async getPersonas(productId?: string): Promise<Persona[]> {
    try {
      const params = productId ? `?product_id=${encodeURIComponent(productId)}` : '';
      const response = await fetch(`${API_BASE_URL}/personas/${params}`);
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

  static async getPersona(personaId: string, productId?: string): Promise<Persona> {
    try {
      const params = productId ? `?product_id=${encodeURIComponent(productId)}` : '';
      const response = await fetch(`${API_BASE_URL}/personas/${personaId}${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch persona: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching persona:', error);
      throw error;
    }
  }

  static async getProducts(): Promise<Product[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/products/`);
      if (!response.ok) {
        throw new Error(`Failed to fetch products: ${response.statusText}`);
      }
      const data: ProductResponse = await response.json();
      return data.products;
    } catch (error) {
      console.error('Error fetching products:', error);
      throw error;
    }
  }

  static async evaluateConversation(payload: EvaluationRequest): Promise<EvaluationResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/evaluations/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Evaluation failed with status ${response.status}`);
      }

      return (await response.json()) as EvaluationResponse;
    } catch (error) {
      console.error('Error evaluating conversation:', error);
      throw error;
    }
  }
}