
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { GoogleGenAI, LiveSession, LiveServerMessage, Modality } from '@google/genai';
import { PERSONAS } from './constants';
import { Persona, AgentStatus, Transcript } from './types';
import { createBlob, decode, decodeAudioData } from './utils/audio';
import { MicrophoneIcon, SpeakerIcon, LoadingSpinner } from './components/Icons';

// Helper component for persona selection
const PersonaSelector: React.FC<{ onSelect: (persona: Persona) => void }> = ({ onSelect }) => (
    <div className="w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl">
        <h2 className="text-3xl font-bold text-center text-brand-light mb-2">Select a Customer Persona</h2>
        <p className="text-center text-brand-accent mb-8">Choose a scenario to start your sales training.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PERSONAS.map((persona) => (
                <button
                    key={persona.id}
                    onClick={() => onSelect(persona)}
                    className="p-6 bg-brand-dark hover:bg-slate-700 rounded-xl text-center transition-all duration-300 transform hover:-translate-y-1 focus:outline-none focus:ring-2 focus:ring-brand-secondary focus:ring-opacity-75"
                >
                    <div className="text-6xl mb-4">{persona.avatar}</div>
                    <h3 className="text-xl font-semibold text-white mb-2">{persona.name}</h3>
                    <p className="text-sm text-slate-400">{persona.description}</p>
                </button>
            ))}
        </div>
    </div>
);

// Helper component for the active simulation view
const SimulationView: React.FC<{
    persona: Persona;
    status: AgentStatus;
    transcripts: Transcript[];
    onEnd: () => void;
}> = ({ persona, status, transcripts, onEnd }) => {
    const transcriptEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcripts]);

    const getStatusIndicator = () => {
        switch (status) {
            case 'connecting':
                return <><LoadingSpinner className="w-6 h-6 mr-2" /> Connecting...</>;
            case 'listening':
                return <><MicrophoneIcon className="w-6 h-6 mr-2 text-green-400 animate-pulse" /> Listening...</>;
            case 'speaking':
                return <><SpeakerIcon className="w-6 h-6 mr-2 text-blue-400 animate-pulse" /> Customer Speaking...</>;
            case 'error':
                 return <span className="text-red-400">Connection Error</span>;
            default:
                return <span className="text-slate-400">Session Idle</span>;
        }
    };
    
    return (
        <div className="w-full h-full flex flex-col max-w-4xl mx-auto p-4 md:p-8 bg-slate-800 rounded-2xl shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-700 pb-4 mb-4">
                <div className='flex items-center'>
                    <span className="text-4xl mr-4">{persona.avatar}</span>
                    <div>
                        <h2 className="text-2xl font-bold text-white">{persona.name}</h2>
                        <p className="text-sm text-brand-accent">{persona.description}</p>
                    </div>
                </div>
                 <div className="text-lg font-medium flex items-center p-2 bg-brand-dark rounded-lg">
                    {getStatusIndicator()}
                 </div>
            </div>
            <div className="flex-grow overflow-y-auto pr-4 space-y-4">
                {transcripts.map((t) => (
                    <div key={t.id} className={`flex items-start gap-3 ${t.speaker === 'Trainee' ? 'justify-end' : 'justify-start'}`}>
                       {t.speaker === 'Customer' && <div className="w-10 h-10 rounded-full bg-brand-primary flex items-center justify-center text-xl flex-shrink-0">{persona.avatar}</div>}
                       <div className={`max-w-md p-3 rounded-xl ${t.speaker === 'Trainee' ? 'bg-brand-secondary text-white' : 'bg-brand-dark text-brand-light'}`}>
                          <p className="font-bold text-sm mb-1">{t.speaker}</p>
                          <p>{t.text}</p>
                       </div>
                       {t.speaker === 'Trainee' && <div className="w-10 h-10 rounded-full bg-brand-secondary flex items-center justify-center flex-shrink-0"><MicrophoneIcon className="w-6 h-6"/></div>}
                    </div>
                ))}
                <div ref={transcriptEndRef} />
            </div>
            <div className="mt-6 flex justify-center">
                <button
                    onClick={onEnd}
                    className="px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-full transition-colors duration-300"
                >
                    End Simulation
                </button>
            </div>
        </div>
    );
};

export default function App() {
    const [selectedPersona, setSelectedPersona] = useState<Persona | null>(null);
    const [isSimulating, setIsSimulating] = useState(false);
    const [status, setStatus] = useState<AgentStatus>('idle');
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);
    
    const sessionRef = useRef<LiveSession | null>(null);
    const inputAudioContextRef = useRef<AudioContext | null>(null);
    const outputAudioContextRef = useRef<AudioContext | null>(null);
    const microphoneStreamRef = useRef<MediaStream | null>(null);
    const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
    const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
    const nextStartTimeRef = useRef<number>(0);

    const currentInputTranscription = useRef('');
    const currentOutputTranscription = useRef('');

    const startSimulation = useCallback(async (persona: Persona) => {
        if (!process.env.API_KEY) {
            alert("API_KEY environment variable not set.");
            return;
        }

        setStatus('connecting');
        setSelectedPersona(persona);
        setIsSimulating(true);

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            microphoneStreamRef.current = stream;

            const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
            
            inputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
            outputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
            nextStartTimeRef.current = 0;

            const sessionPromise = ai.live.connect({
                model: 'gemini-2.5-flash-native-audio-preview-09-2025',
                config: {
                    responseModalities: [Modality.AUDIO],
                    speechConfig: {
                        voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
                    },
                    systemInstruction: persona.systemInstruction,
                    inputAudioTranscription: {},
                    outputAudioTranscription: {},
                },
                callbacks: {
                    onopen: () => {
                        const inputAudioContext = inputAudioContextRef.current;
                        if (!inputAudioContext || !microphoneStreamRef.current) return;

                        const source = inputAudioContext.createMediaStreamSource(microphoneStreamRef.current);
                        const scriptProcessor = inputAudioContext.createScriptProcessor(4096, 1, 1);
                        scriptProcessorRef.current = scriptProcessor;

                        scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
                            const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);
                            const pcmBlob = createBlob(inputData);
                            sessionPromise.then((session) => {
                                session.sendRealtimeInput({ media: pcmBlob });
                            });
                        };
                        source.connect(scriptProcessor);
                        scriptProcessor.connect(inputAudioContext.destination);
                        setStatus('listening');
                    },
                    onmessage: async (message: LiveServerMessage) => {
                       if (message.serverContent?.outputTranscription) {
                            const text = message.serverContent.outputTranscription.text;
                            currentOutputTranscription.current += text;
                        }
                        
                        if (message.serverContent?.inputTranscription) {
                            const text = message.serverContent.inputTranscription.text;
                            currentInputTranscription.current += text;
                        }

                        if (message.serverContent?.turnComplete) {
                            const fullInput = currentInputTranscription.current.trim();
                            const fullOutput = currentOutputTranscription.current.trim();
                            
                            setTranscripts(prev => {
                                let newTranscripts = [...prev];
                                if (fullInput) {
                                    newTranscripts.push({ id: Date.now(), speaker: 'Trainee', text: fullInput });
                                }
                                if (fullOutput) {
                                    newTranscripts.push({ id: Date.now() + 1, speaker: 'Customer', text: fullOutput });
                                }
                                return newTranscripts;
                            });
                            
                            currentInputTranscription.current = '';
                            currentOutputTranscription.current = '';
                        }
                        
                        const base64Audio = message.serverContent?.modelTurn?.parts[0]?.inlineData?.data;
                        if (base64Audio && outputAudioContextRef.current) {
                            setStatus('speaking');
                            const outputAudioContext = outputAudioContextRef.current;
                            nextStartTimeRef.current = Math.max(nextStartTimeRef.current, outputAudioContext.currentTime);

                            const audioBuffer = await decodeAudioData(decode(base64Audio), outputAudioContext, 24000, 1);
                            
                            const source = outputAudioContext.createBufferSource();
                            source.buffer = audioBuffer;
                            source.connect(outputAudioContext.destination);
                            
                            source.addEventListener('ended', () => {
                                sourcesRef.current.delete(source);
                                if (sourcesRef.current.size === 0) {
                                    setStatus('listening');
                                }
                            });
                            
                            source.start(nextStartTimeRef.current);
                            nextStartTimeRef.current += audioBuffer.duration;
                            sourcesRef.current.add(source);
                        }

                        if (message.serverContent?.interrupted) {
                            for (const source of sourcesRef.current.values()) {
                                source.stop();
                            }
                            sourcesRef.current.clear();
                            nextStartTimeRef.current = 0;
                            setStatus('listening');
                        }
                    },
                    onerror: (e: ErrorEvent) => {
                        console.error('Session error:', e);
                        setStatus('error');
                    },
                    onclose: (e: CloseEvent) => {
                        console.log('Session closed');
                        setStatus('idle');
                    },
                },
            });
            sessionRef.current = await sessionPromise;

        } catch (error) {
            console.error("Failed to start simulation:", error);
            setStatus('error');
            alert("Could not start audio. Please check microphone permissions.");
            endSimulation();
        }
    }, []);

    const endSimulation = useCallback(() => {
        sessionRef.current?.close();
        sessionRef.current = null;

        scriptProcessorRef.current?.disconnect();
        scriptProcessorRef.current = null;
        
        microphoneStreamRef.current?.getTracks().forEach(track => track.stop());
        microphoneStreamRef.current = null;
        
        inputAudioContextRef.current?.close();
        outputAudioContextRef.current?.close();
        inputAudioContextRef.current = null;
        outputAudioContextRef.current = null;
        
        sourcesRef.current.clear();

        setIsSimulating(false);
        setSelectedPersona(null);
        setTranscripts([]);
        setStatus('idle');
    }, []);
    
    useEffect(() => {
        // Cleanup on unmount
        return () => {
            if(isSimulating) {
                endSimulation();
            }
        };
    }, [isSimulating, endSimulation]);

    return (
        <main className="min-h-screen w-full flex flex-col items-center justify-center p-4 bg-gradient-to-br from-brand-dark to-slate-900 font-sans">
            {!isSimulating || !selectedPersona ? (
                <>
                 <h1 className="text-5xl font-extrabold text-center text-white mb-4">AI Sales Training Simulator</h1>
                  <p className="text-xl text-center text-brand-accent mb-12 max-w-2xl">Practice real-world sales conversations with an AI-powered customer. Hone your skills in a safe, interactive environment.</p>
                 <PersonaSelector onSelect={startSimulation} />
                </>
            ) : (
                <div className="w-full h-[90vh] max-h-[800px]">
                    <SimulationView 
                        persona={selectedPersona} 
                        status={status} 
                        transcripts={transcripts}
                        onEnd={endSimulation} 
                    />
                </div>
            )}
        </main>
    );
}
