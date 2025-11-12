import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Persona, AgentStatus, TranscriptMessage, ApiService } from './services/api';
import { WebSocketService } from './services/websocket';
import { decode, decodeAudioData } from './utils/audio';
import { MicrophoneIcon, SpeakerIcon, LoadingSpinner } from './components/Icons';

// Helper component for persona selection
const PersonaSelector: React.FC<{ onSelect: (persona: Persona) => void }> = ({ onSelect }) => {
    const [personas, setPersonas] = useState<Persona[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPersonas = async () => {
            try {
                const fetchedPersonas = await ApiService.getPersonas();
                setPersonas(fetchedPersonas);
            } catch (err) {
                setError('Failed to load personas');
                console.error('Error fetching personas:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchPersonas();
    }, []);

    if (loading) {
        return (
            <div className="w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
                <LoadingSpinner className="w-8 h-8 mx-auto mb-4" />
                <p className="text-brand-accent">Loading personas...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
                <p className="text-red-400">{error}</p>
            </div>
        );
    }

    return (
        <div className="w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl">
            <h2 className="text-3xl font-bold text-center text-brand-light mb-2">Select a Customer Persona</h2>
            <p className="text-center text-brand-accent mb-8">Choose a scenario to start your sales training.</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {personas.map((persona) => (
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
};

// Helper component for the active simulation view
const SimulationView: React.FC<{
    persona: Persona;
    status: AgentStatus;
    transcripts: TranscriptMessage[];
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
    // Manual stop listening handler
    const handleStopListening = useCallback(() => {
        console.log('[App] Stop Listening button pressed');
        // Notify backend to stop listening if connected
        if (wsServiceRef.current && wsServiceRef.current.isConnected()) {
            wsServiceRef.current.sendStopListening();
        }
        // Clear any pending start request and disable local audio capture immediately
        pendingStartListeningRef.current = false;
        isListeningRef.current = false;
        setIsListening(false);
        if (workletNodeRef.current) {
            workletNodeRef.current.port.postMessage({ type: 'setListening', value: false });
        }
    }, []);
    const [selectedPersona, setSelectedPersona] = useState<Persona | null>(null);
    const [isSimulating, setIsSimulating] = useState(false);
    const [status, setStatus] = useState<AgentStatus>('idle');
    const [transcripts, setTranscripts] = useState<TranscriptMessage[]>([]);

    const wsServiceRef = useRef<WebSocketService | null>(null);
    const inputAudioContextRef = useRef<AudioContext | null>(null);
    const outputAudioContextRef = useRef<AudioContext | null>(null);
    const microphoneStreamRef = useRef<MediaStream | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
    const nextStartTimeRef = useRef<number>(0);
    const nextTranscriptIdRef = useRef<number>(0);
    const isListeningRef = useRef<boolean>(false);
    const [isListening, setIsListening] = useState(false);

    // Track if worklet is ready
    const [workletReady, setWorkletReady] = useState(false);
    // Track if user has requested listening
    const pendingStartListeningRef = useRef(false);
    // Manual start listening handler
    const handleStartListening = useCallback(() => {
        console.log('[App] Start Listening button pressed');
        // Attempt to notify backend to start listening
        if (wsServiceRef.current && wsServiceRef.current.isConnected()) {
            wsServiceRef.current.sendStartListening();
        }
        // Mark that user requested start; enable local audio capture immediately so the UI
        // is responsive (un-gray the buttons). If backend later confirms, nothing changes.
        pendingStartListeningRef.current = true;
        isListeningRef.current = true;
        setIsListening(true);
        if (workletNodeRef.current) {
            workletNodeRef.current.port.postMessage({ type: 'setListening', value: true });
        }
    }, []);

    const startSimulation = useCallback(async (persona: Persona) => {
        setStatus('connecting');
        setSelectedPersona(persona);
        setIsSimulating(true);
        setTranscripts([]);

        try {
            // Get microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            microphoneStreamRef.current = stream;

            // Set up audio contexts
            inputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
            outputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
            nextStartTimeRef.current = 0;

            // Create WebSocket service
            wsServiceRef.current = new WebSocketService(
                (newStatus: AgentStatus) => {
                    setStatus(newStatus);
                    // If backend confirms listening, clear pending flag and ensure local capture is enabled
                    if (newStatus === 'listening') {
                        console.log('[App] Backend status is listening');
                        pendingStartListeningRef.current = false;
                        isListeningRef.current = true;
                        setIsListening(true);
                        if (workletNodeRef.current) {
                            workletNodeRef.current.port.postMessage({ type: 'setListening', value: true });
                        }
                    } else if (newStatus === 'idle' || newStatus === 'error') {
                        // If backend drops to idle or an error occurs, clear pending and disable local capture
                        pendingStartListeningRef.current = false;
                        isListeningRef.current = false;
                        setIsListening(false);
                        if (workletNodeRef.current) {
                            workletNodeRef.current.port.postMessage({ type: 'setListening', value: false });
                        }
                    }
                },
                (transcript: TranscriptMessage) => {
                    setTranscripts(prev => {
                        // Helper to merge incoming transcript chunks with existing text while
                        // avoiding duplication from overlapping partial/final chunks.
                        const mergeTranscript = (existingText: string, incoming: string) => {
                            if (!incoming) return existingText;
                            if (!existingText) return incoming;
                            // Exact match -> keep existing
                            if (existingText === incoming) return existingText;
                            // If existing already ends with the incoming chunk, skip
                            if (existingText.endsWith(incoming)) return existingText;
                            // If incoming starts with existing, incoming contains existing as prefix -> return incoming (longer)
                            if (incoming.startsWith(existingText)) return incoming;

                            // Find the largest overlap where the end of existing matches the start of incoming
                            const maxOverlap = Math.min(existingText.length, incoming.length);
                            for (let k = maxOverlap; k > 0; k--) {
                                if (existingText.endsWith(incoming.substring(0, k))) {
                                    return existingText + incoming.substring(k);
                                }
                            }

                            // No overlap found -> concatenate
                            return existingText + incoming;
                        };

                        // Only stream for Customer (AI) messages
                        if (transcript.speaker === 'Customer') {
                            // Find last AI message
                            const lastIdx = prev.length - 1;
                            if (
                                lastIdx >= 0 &&
                                prev[lastIdx].speaker === 'Customer' &&
                                !prev[lastIdx].is_final
                            ) {
                                // Update last message but avoid duplicating repeated chunks
                                const updated = [...prev];
                                updated[lastIdx] = {
                                    ...updated[lastIdx],
                                    text: mergeTranscript(updated[lastIdx].text, transcript.text),
                                    is_final: transcript.is_final,
                                };
                                return updated;
                            } else {
                                // Avoid adding a new message if the last message already has identical text
                                const lastIdx2 = prev.length - 1;
                                if (lastIdx2 >= 0 && prev[lastIdx2].text === transcript.text && prev[lastIdx2].speaker === 'Customer') {
                                    return prev;
                                }
                                // Add new streaming message
                                return [
                                    ...prev,
                                    {
                                        ...transcript,
                                        id: nextTranscriptIdRef.current++,
                                    },
                                ];
                            }
                        } else {
                            // For Trainee (user), stream into last message if not final
                            const lastIdx = prev.length - 1;
                            if (
                                lastIdx >= 0 &&
                                prev[lastIdx].speaker === 'Trainee' &&
                                !prev[lastIdx].is_final
                            ) {
                                const updated = [...prev];
                                updated[lastIdx] = {
                                    ...updated[lastIdx],
                                    text: mergeTranscript(updated[lastIdx].text, transcript.text),
                                    is_final: transcript.is_final,
                                };
                                return updated;
                            } else {
                                // Avoid adding a new message if the last message already has identical text
                                const lastIdx2 = prev.length - 1;
                                if (lastIdx2 >= 0 && prev[lastIdx2].text === transcript.text && prev[lastIdx2].speaker === 'Trainee') {
                                    return prev;
                                }
                                // Add new streaming message
                                return [
                                    ...prev,
                                    {
                                        ...transcript,
                                        id: nextTranscriptIdRef.current++,
                                    },
                                ];
                            }
                        }
                    });
                },
                async (
                    audioData: string,
                    mimeType?: string,
                    sampleRate?: number,
                    channels?: number,
                    bitRate?: number,
                    codec?: string,
                    bitDepth?: number,
                    encoding?: string
                ) => {
                    // Handle incoming audio from backend
                    console.log('[App] Received audio data from backend');
                    console.debug('[App] audio metadata', { mimeType, sampleRate, channels, bitRate, codec, bitDepth, encoding });
                    if (outputAudioContextRef.current) {
                        const outputAudioContext = outputAudioContextRef.current;
                        nextStartTimeRef.current = Math.max(nextStartTimeRef.current, outputAudioContext.currentTime);

                        let audioBuffer: AudioBuffer | null = null;
                        try {
                            // Treat any 'mp3' or 'mpeg' mime types as MP3
                            if (mimeType && (mimeType.includes('mp3') || mimeType.includes('mpeg'))) {
                                // MP3: decode using decodeAudioData
                                const uint8 = decode(audioData);
                                // Create an ArrayBuffer view containing only the audio bytes
                                const arrayBuffer = uint8.buffer.slice(uint8.byteOffset, uint8.byteOffset + uint8.byteLength) as ArrayBuffer;
                                audioBuffer = await outputAudioContext.decodeAudioData(arrayBuffer);
                            } else {
                                // Default to PCM Int16
                                audioBuffer = await decodeAudioData(
                                    decode(audioData),
                                    outputAudioContext,
                                    sampleRate || 24000,
                                    channels || 1
                                );
                            }
                        } catch (err) {
                            console.error('Audio decode error:', err, { mimeType, sampleRate, channels });
                            return;
                        }

                        if (audioBuffer) {
                            const source = outputAudioContext.createBufferSource();
                            source.buffer = audioBuffer;
                            source.connect(outputAudioContext.destination);

                            source.addEventListener('ended', () => {
                                sourcesRef.current.delete(source);
                                if (sourcesRef.current.size === 0) {
                                    console.log('[App] All audio sources ended, setting status to listening');
                                    setStatus('listening');
                                    // Do not automatically re-enable or disable listening; only user controls it
                                }
                            });

                            source.start(nextStartTimeRef.current);
                            nextStartTimeRef.current += audioBuffer.duration;
                            sourcesRef.current.add(source);
                            // Do not disable listening while AI is speaking; only user controls it
                        }
                    }
                },
                (error: string) => {
                    console.error('WebSocket error:', error);
                    setStatus('error');
                }
            );

            // Connect to WebSocket
            const connected = await wsServiceRef.current.connect(persona.id);
            if (!connected) {
                throw new Error('Failed to connect to backend');
            }

            // Set up microphone audio processing using AudioWorklet
            const inputAudioContext = inputAudioContextRef.current;
            if (inputAudioContext && microphoneStreamRef.current) {
                const source = inputAudioContext.createMediaStreamSource(microphoneStreamRef.current);

                // Load and use AudioWorklet instead of ScriptProcessorNode
                await inputAudioContext.audioWorklet.addModule('/audio-processor.js');
                const workletNode = new AudioWorkletNode(inputAudioContext, 'audio-processor');
                workletNodeRef.current = workletNode;

                // Start with listening disabled; user must click button
                isListeningRef.current = false;
                setIsListening(false);
                workletNode.port.postMessage({ type: 'setListening', value: false });

                workletNode.port.onmessage = (event) => {
                    console.log('[App] workletNode.port.onmessage fired');
                    // Send audio data via WebSocket only if we're actively listening
                    if (wsServiceRef.current && isListeningRef.current) {
                        console.log('[App] Sending audio data to WebSocket');
                        // Convert Int16Array to base64 string
                        const int16Array = event.data;
                        const uint8Array = new Uint8Array(int16Array.buffer, int16Array.byteOffset, int16Array.byteLength);
                        const base64String = btoa(String.fromCharCode(...uint8Array));
                        wsServiceRef.current.sendAudio(base64String, 'audio/pcm;rate=16000');
                    } else {
                        console.log('[App] Not sending audio: isListeningRef.current =', isListeningRef.current);
                    }
                };

                source.connect(workletNode);
                workletNode.connect(inputAudioContext.destination);
                setWorkletReady(true);
            }

        } catch (error) {
            console.error("Failed to start simulation:", error);
            setStatus('error');
            alert("Could not start audio. Please check microphone permissions and backend connection.");
            endSimulation();
        }
    }, []);

    const endSimulation = useCallback(() => {
        console.log('[App] Ending simulation and resetting to first screen');

        // Disable listening immediately
        isListeningRef.current = false;
        if (workletNodeRef.current) {
            workletNodeRef.current.port.postMessage({ type: 'setListening', value: false });
        }

        // Close WebSocket connection
        if (wsServiceRef.current) {
            wsServiceRef.current.endSession();
            wsServiceRef.current = null;
        }

        // Clean up audio
        workletNodeRef.current?.disconnect();
        workletNodeRef.current = null;

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
        nextTranscriptIdRef.current = 0;
        isListeningRef.current = false;
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
                <div className="w-full h-[90vh] max-h-[800px] flex flex-col">
                    <SimulationView 
                        persona={selectedPersona} 
                        status={status} 
                        transcripts={transcripts}
                        onEnd={endSimulation} 
                    />
                    <div className="flex justify-center mt-4 gap-4">
                        <button
                            className={`px-8 py-3 bg-green-600 hover:bg-green-700 text-white font-bold rounded-full transition-colors duration-300 ${isListening || status === 'speaking' || !workletReady ? 'opacity-50 cursor-not-allowed' : ''}`}
                            onClick={handleStartListening}
                            disabled={isListening || status === 'speaking' || !workletReady}
                        >
                            <MicrophoneIcon className="w-6 h-6 mr-2 inline-block" /> {isListening ? 'Listening...' : !workletReady ? 'Initializing...' : 'Start Listening'}
                        </button>
                        <button
                            className={`px-8 py-3 bg-gray-600 hover:bg-gray-700 text-white font-bold rounded-full transition-colors duration-300 ${!isListening ? 'opacity-50 cursor-not-allowed' : ''}`}
                            onClick={handleStopListening}
                            disabled={!isListening}
                        >
                            Stop Listening
                        </button>
                    </div>
                </div>
            )}
        </main>
    );
}
