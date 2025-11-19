import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
    Persona,
    AgentStatus,
    TranscriptMessage,
    ApiService,
    Product,
    EvaluationResponse,
} from './services/api';
import { WebSocketService } from './services/websocket';
import { decode, decodeAudioData } from './utils/audio';
import { MicrophoneIcon, SpeakerIcon, LoadingSpinner } from './components/Icons';
import { EvaluationReport } from './components/EvaluationReport';

const ProductSelector: React.FC<{ onSelect: (product: Product) => void }> = ({ onSelect }) => {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchProducts = async () => {
            try {
                const fetchedProducts = await ApiService.getProducts();
                setProducts(fetchedProducts);
            } catch (err) {
                setError('Failed to load products');
                console.error('Error fetching products:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchProducts();
    }, []);

    if (loading) {
        return (
            <div className="w-full max-w-5xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
                <LoadingSpinner className="w-8 h-8 mx-auto mb-4" />
                <p className="text-brand-accent">Loading products...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="w-full max-w-5xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
                <p className="text-red-400">{error}</p>
            </div>
        );
    }

    return (
        <div className="w-full max-w-5xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl">
            <h2 className="text-3xl font-bold text-center text-brand-light mb-2">Select the Product You&apos;re Selling</h2>
            <p className="text-center text-brand-accent mb-8">Pick a product to tailor the customer scenario.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {products.map((product) => (
                    <button
                        key={product.id}
                        onClick={() => onSelect(product)}
                        className="p-6 bg-brand-dark hover:bg-slate-700 rounded-xl text-left transition-all duration-300 transform hover:-translate-y-1 focus:outline-none focus:ring-2 focus:ring-brand-secondary focus:ring-opacity-75"
                    >
                        <div className="flex flex-col gap-3">
                            <div className="flex items-start justify-between gap-4">
                                <div>
                                    <h3 className="text-xl font-semibold text-white">{product.name}</h3>
                                    {product.tagline && <p className="text-sm text-brand-accent mt-1">{product.tagline}</p>}
                                </div>
                                {product.price && (
                                    <span className="bg-brand-secondary text-white text-sm font-semibold px-3 py-1 rounded-full">{product.price}</span>
                                )}
                            </div>
                            {product.description && <p className="text-sm text-slate-300">{product.description}</p>}
                            {product.key_benefits?.length ? (
                                <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                                    {product.key_benefits.slice(0, 3).map((benefit) => (
                                        <li key={benefit}>{benefit}</li>
                                    ))}
                                </ul>
                            ) : null}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
};

const ProductDetailsCard: React.FC<{ product: Product; className?: string }> = ({ product, className = '' }) => (
    <div className={`bg-brand-dark border border-slate-700 rounded-xl p-4 text-brand-light ${className}`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
                <h3 className="text-xl font-semibold text-white">{product.name}</h3>
                {product.tagline && <p className="text-sm text-brand-accent mt-1">{product.tagline}</p>}
            </div>
            {product.price && <span className="bg-brand-secondary text-white text-sm font-semibold px-3 py-1 rounded-full">{product.price}</span>}
        </div>
        {product.description && <p className="mt-3 text-sm text-slate-300">{product.description}</p>}
        {product.key_benefits?.length ? (
            <ul className="mt-3 list-disc list-inside text-sm text-slate-300 space-y-1">
                {product.key_benefits.map((benefit) => (
                    <li key={benefit}>{benefit}</li>
                ))}
            </ul>
        ) : null}
        {product.usage_notes && (
            <p className="mt-3 text-xs text-slate-400 italic">Usage notes: {product.usage_notes}</p>
        )}
    </div>
);

// Helper component for persona selection
const PersonaSelector: React.FC<{ product: Product; onSelect: (persona: Persona) => void }> = ({ product, onSelect }) => {
    const [personas, setPersonas] = useState<Persona[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPersonas = async () => {
            setLoading(true);
            setError(null);
            try {
                const fetchedPersonas = await ApiService.getPersonas(product.id);
                setPersonas(fetchedPersonas);
            } catch (err) {
                setError('Failed to load personas');
                console.error('Error fetching personas:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchPersonas();
    }, [product.id]);

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
            <p className="text-center text-brand-accent mb-8">You&apos;re pitching <span className="font-semibold text-white">{product.name}</span>. Pick who you&apos;re talking to.</p>
            <ProductDetailsCard product={product} />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
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
    product: Product;
    status: AgentStatus;
    transcripts: TranscriptMessage[];
    onEnd: () => void | Promise<void>;
    isEnding: boolean;
    sessionEnded: boolean;
}> = ({ persona, product, status, transcripts, onEnd, isEnding, sessionEnded }) => {
    const transcriptEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcripts]);

    const getStatusIndicator = () => {
        if (sessionEnded) {
            return <span className="text-brand-accent">Session complete</span>;
        }

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
        <div className="w-full h-full max-w-7xl mx-auto flex flex-col xl:flex-row gap-6">
            <section className="flex-1 xl:flex-[1.2] flex flex-col bg-slate-800 rounded-2xl shadow-2xl p-4 md:p-8">
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
                    {transcripts.map((t, index) => (
                        <div key={t.id ?? `transcript-${index}`} className={`flex items-start gap-3 ${t.speaker === 'Trainee' ? 'justify-end' : 'justify-start'}`}>
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
                <div className="mt-6 flex justify-center min-h-[48px]">
                    {!sessionEnded ? (
                        <button
                            onClick={onEnd}
                            disabled={isEnding}
                            className={`px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-full transition-colors duration-300 flex items-center gap-2 ${isEnding ? 'opacity-75 cursor-not-allowed' : ''}`}
                        >
                            {isEnding ? (
                                <>
                                    <LoadingSpinner className="w-5 h-5" />
                                    <span>Ending...</span>
                                </>
                            ) : (
                                'End Simulation'
                            )}
                        </button>
                    ) : (
                        <p className="text-sm text-slate-400">Conversation ended. Review the evaluation below.</p>
                    )}
                </div>
            </section>
            <aside className="w-full xl:w-80 2xl:w-96 xl:flex-shrink-0">
                <ProductDetailsCard product={product} className="shadow-2xl xl:sticky xl:top-4" />
            </aside>
        </div>
    );
};

export default function App() {
    const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
    const [selectedPersona, setSelectedPersona] = useState<Persona | null>(null);
    const [isSimulating, setIsSimulating] = useState(false);
    const [status, setStatus] = useState<AgentStatus>('idle');
    const [transcripts, setTranscripts] = useState<TranscriptMessage[]>([]);
    const [evaluationResult, setEvaluationResult] = useState<EvaluationResponse | null>(null);
    const [evaluationStatus, setEvaluationStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
    const [evaluationError, setEvaluationError] = useState<string | null>(null);
    const [sessionEnded, setSessionEnded] = useState(false);
    const [isEndingSimulation, setIsEndingSimulation] = useState(false);

    const wsServiceRef = useRef<WebSocketService | null>(null);
    const inputAudioContextRef = useRef<AudioContext | null>(null);
    const outputAudioContextRef = useRef<AudioContext | null>(null);
    const microphoneStreamRef = useRef<MediaStream | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
    const nextStartTimeRef = useRef<number>(0);
    const nextTranscriptIdRef = useRef<number>(0);
    const captureAudioRef = useRef<boolean>(false);
    const captureTimeoutRef = useRef<number | null>(null);
    const [micMuted, setMicMuted] = useState(false);

    // Track if worklet is ready
    const [workletReady, setWorkletReady] = useState(false);

    const stopAllPlayback = useCallback(() => {
        sourcesRef.current.forEach((source) => {
            try {
                source.stop();
            } catch (err) {
                console.debug('[App] Audio source stop error', err);
            }
        });
        sourcesRef.current.clear();
        if (outputAudioContextRef.current) {
            const ctx = outputAudioContextRef.current;
            nextStartTimeRef.current = ctx.currentTime;
        }
    }, []);

    const handleAudioStop = useCallback((reason?: string) => {
        console.debug('[App] Received audio stop signal', reason);
        stopAllPlayback();
        setStatus((prev) => (prev === 'speaking' ? 'listening' : prev));
    }, [stopAllPlayback]);

    const handleProductSelect = useCallback((product: Product) => {
        if (isSimulating) {
            return;
        }
        stopAllPlayback();
        if (wsServiceRef.current) {
            wsServiceRef.current.disconnect();
            wsServiceRef.current = null;
        }
        setSelectedProduct(product);
        setSelectedPersona(null);
        setTranscripts([]);
        setStatus('idle');
        setEvaluationResult(null);
        setEvaluationStatus('idle');
        setEvaluationError(null);
        setSessionEnded(false);
        setIsEndingSimulation(false);
        nextTranscriptIdRef.current = 0;
    }, [isSimulating, stopAllPlayback]);

    const handleChangeProduct = useCallback(() => {
        if (isSimulating) {
            alert('Please end the current simulation before changing products.');
            return;
        }
        stopAllPlayback();
        if (wsServiceRef.current) {
            wsServiceRef.current.disconnect();
            wsServiceRef.current = null;
        }
        setSelectedProduct(null);
        setSelectedPersona(null);
        setTranscripts([]);
        setStatus('idle');
        setEvaluationResult(null);
        setEvaluationStatus('idle');
        setEvaluationError(null);
        setSessionEnded(false);
        setIsEndingSimulation(false);
        nextTranscriptIdRef.current = 0;
    }, [isSimulating, stopAllPlayback]);

    const updateWorkletListening = useCallback((value: boolean) => {
        captureAudioRef.current = value;
        if (workletNodeRef.current) {
            workletNodeRef.current.port.postMessage({ type: 'setListening', value });
        }
    }, []);

    useEffect(() => {
        const clearPendingTimeout = () => {
            if (captureTimeoutRef.current !== null) {
                window.clearTimeout(captureTimeoutRef.current);
                captureTimeoutRef.current = null;
            }
        };

        if (!isSimulating || !workletReady || micMuted || status === 'error') {
            clearPendingTimeout();
            updateWorkletListening(false);
        } else if (status === 'listening') {
            clearPendingTimeout();
            updateWorkletListening(true);
        } else if (captureTimeoutRef.current === null) {
            captureTimeoutRef.current = window.setTimeout(() => {
                updateWorkletListening(false);
                captureTimeoutRef.current = null;
            }, 3000);
        }

        return clearPendingTimeout;
    }, [isSimulating, workletReady, micMuted, status, updateWorkletListening]);

    const terminateActiveSession = useCallback(() => {
        console.log('[App] Terminating active session resources');

        if (captureTimeoutRef.current !== null) {
            window.clearTimeout(captureTimeoutRef.current);
            captureTimeoutRef.current = null;
        }

        updateWorkletListening(false);
        setMicMuted(false);
        stopAllPlayback();

        if (wsServiceRef.current) {
            wsServiceRef.current.endSession();
            wsServiceRef.current = null;
        }

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
        setStatus('idle');
        setWorkletReady(false);
    }, [stopAllPlayback, updateWorkletListening]);

    const startSimulation = useCallback(async (persona: Persona) => {
        if (!selectedProduct) {
            alert('Please select a product before starting the simulation.');
            return;
        }

        setEvaluationResult(null);
        setEvaluationStatus('idle');
        setEvaluationError(null);
        setSessionEnded(false);
        setIsEndingSimulation(false);
        setMicMuted(false);
        setStatus('connecting');
        setSelectedPersona(persona);
        setIsSimulating(true);
        setTranscripts([]);
        nextTranscriptIdRef.current = 0;

        const product = selectedProduct;

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
                },
                (transcript: TranscriptMessage) => {
                    setTranscripts(prev => {
                        const incomingId = transcript.id;
                        if (typeof incomingId === 'number') {
                            nextTranscriptIdRef.current = Math.max(nextTranscriptIdRef.current, incomingId + 1);
                        }

                        // Helper to merge incoming transcript chunks with existing text while
                        // avoiding duplication from overlapping partial/final chunks.
                        const mergeTranscript = (
                            existingText: string,
                            incoming: string,
                            speakerLabel: TranscriptMessage['speaker'],
                            isFinal: boolean
                        ) => {
                            if (isFinal) {
                                return incoming;
                            }

                            if (!incoming) {
                                return existingText;
                            }
                            if (!existingText) {
                                return incoming;
                            }
                            if (speakerLabel === 'Trainee') {
                                if (existingText === incoming) {
                                    return existingText;
                                }
                                if (incoming.includes(existingText)) {
                                    return incoming;
                                }
                                if (existingText.includes(incoming)) {
                                    return existingText;
                                }
                                return incoming;
                            }

                            if (existingText === incoming) {
                                return existingText;
                            }
                            if (existingText.endsWith(incoming)) {
                                return existingText;
                            }
                            if (incoming.startsWith(existingText)) {
                                return incoming;
                            }

                            const sanitizedExisting = existingText.trimEnd();
                            const sanitizedIncoming = incoming.trimStart();
                            const maxOverlap = Math.min(sanitizedExisting.length, sanitizedIncoming.length);
                            for (let k = maxOverlap; k > 0; k--) {
                                if (sanitizedExisting.endsWith(sanitizedIncoming.substring(0, k))) {
                                    return `${sanitizedExisting}${sanitizedIncoming.substring(k)}`;
                                }
                            }

                            return `${sanitizedExisting} ${sanitizedIncoming}`.replace(/\s+/g, ' ').trim();
                        };

                        const updateEntryAt = (index: number) => {
                            const updated = [...prev];
                            const existing = updated[index];
                            const isFinal = transcript.is_final ?? existing.is_final ?? false;
                            const mergedText = mergeTranscript(existing.text, transcript.text, transcript.speaker, isFinal);
                            const confidence = transcript.confidence ?? existing.confidence;

                            if (existing.text === mergedText && existing.is_final === isFinal && existing.confidence === confidence) {
                                return prev;
                            }

                            updated[index] = {
                                ...existing,
                                text: mergedText,
                                is_final: isFinal,
                                confidence
                            };
                            return updated;
                        };

                        if (typeof incomingId === 'number') {
                            const targetIndex = prev.findIndex(message => message.id === incomingId && message.speaker === transcript.speaker);
                            if (targetIndex >= 0) {
                                return updateEntryAt(targetIndex);
                            }
                        }

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
                                return updateEntryAt(lastIdx);
                            } else {
                                // Avoid adding a new message if the last message already has identical text
                                const lastIdx2 = prev.length - 1;
                                if (lastIdx2 >= 0 && prev[lastIdx2].text === transcript.text && prev[lastIdx2].speaker === 'Customer') {
                                    return prev;
                                }
                                // Add new streaming message
                                const resolvedId = typeof incomingId === 'number' ? incomingId : nextTranscriptIdRef.current++;
                                nextTranscriptIdRef.current = Math.max(nextTranscriptIdRef.current, resolvedId + 1);
                                return [
                                    ...prev,
                                    {
                                        ...transcript,
                                        id: resolvedId,
                                        is_final: transcript.is_final ?? false
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
                                return updateEntryAt(lastIdx);
                            } else {
                                const lastIdx2 = prev.length - 1;
                                if (lastIdx2 >= 0 && prev[lastIdx2].text === transcript.text && prev[lastIdx2].speaker === 'Trainee') {
                                    return prev;
                                }
                                // Add new streaming message
                                const resolvedId = typeof incomingId === 'number' ? incomingId : nextTranscriptIdRef.current++;
                                nextTranscriptIdRef.current = Math.max(nextTranscriptIdRef.current, resolvedId + 1);
                                return [
                                    ...prev,
                                    {
                                        ...transcript,
                                        id: resolvedId,
                                        is_final: transcript.is_final ?? false
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
                    console.debug('[App] Received audio data from backend');
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
                                    console.debug('[App] All audio sources ended, setting status to listening');
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
                handleAudioStop,
                (error: string) => {
                    console.error('WebSocket error:', error);
                    setStatus('error');
                }
            );

            // Connect to WebSocket
            const connected = await wsServiceRef.current.connect(persona.id, product.id);
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

                // Start with capture disabled; effect will enable when ready
                updateWorkletListening(false);

                workletNode.port.onmessage = (event) => {
                    console.debug('[App] workletNode.port.onmessage fired');
                    // Send audio data via WebSocket only if we're actively listening
                    if (wsServiceRef.current && captureAudioRef.current) {
                        console.debug('[App] Sending audio data to WebSocket');
                        // Convert Int16Array to base64 string
                        const int16Array = event.data;
                        const uint8Array = new Uint8Array(int16Array.buffer, int16Array.byteOffset, int16Array.byteLength);
                        const base64String = btoa(String.fromCharCode(...uint8Array));
                        wsServiceRef.current.sendAudio(base64String, 'audio/pcm;rate=16000');
                    } else {
                        console.debug('[App] Not sending audio: captureAudioRef.current =', captureAudioRef.current);
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
            terminateActiveSession();
        }
    }, [handleAudioStop, selectedProduct, terminateActiveSession, updateWorkletListening]);

    const evaluateConversation = useCallback(async () => {
        const persona = selectedPersona;
        if (!persona) {
            setEvaluationStatus('error');
            setEvaluationError('No persona selected for evaluation.');
            return;
        }

        const meaningfulTranscripts = transcripts.filter((message) => {
            if (message.is_final === false) {
                return false;
            }
            return Boolean(message.text && message.text.trim());
        });

        if (!meaningfulTranscripts.length) {
            setEvaluationStatus('error');
            setEvaluationError('No transcript content was captured for evaluation.');
            return;
        }

        try {
            const response = await ApiService.evaluateConversation({
                persona_id: persona.id,
                product_id: selectedProduct?.id,
                transcript: meaningfulTranscripts,
            });
            setEvaluationResult(response);
            setEvaluationStatus('success');
        } catch (error) {
            console.error('Evaluation request failed:', error);
            const message = error instanceof Error ? error.message : 'Failed to generate evaluation report.';
            setEvaluationStatus('error');
            setEvaluationError(message);
        }
    }, [selectedPersona, selectedProduct, transcripts]);

    const endSimulation = useCallback(async () => {
        if (isEndingSimulation) {
            return;
        }

        setIsEndingSimulation(true);
        setSessionEnded(true);
        setEvaluationStatus('loading');
        setEvaluationError(null);
        setEvaluationResult(null);

        terminateActiveSession();

        try {
            await evaluateConversation();
        } finally {
            setIsEndingSimulation(false);
        }
    }, [evaluateConversation, isEndingSimulation, terminateActiveSession]);

    const retryEvaluation = useCallback(async () => {
        setEvaluationStatus('loading');
        setEvaluationError(null);
        setEvaluationResult(null);
        await evaluateConversation();
    }, [evaluateConversation]);

    const handleDownloadReport = useCallback(() => {
        if (!evaluationResult) {
            return;
        }

        const payload = {
            ...evaluationResult,
            transcript: transcripts,
        };

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `sales-evaluation-${evaluationResult.report_id}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
    }, [evaluationResult, transcripts]);

    const startNewSimulation = useCallback(() => {
        terminateActiveSession();
        setEvaluationStatus('idle');
        setEvaluationResult(null);
        setEvaluationError(null);
        setSessionEnded(false);
        setIsEndingSimulation(false);
        setSelectedPersona(null);
        setTranscripts([]);
        setStatus('idle');
        nextTranscriptIdRef.current = 0;
    }, [terminateActiveSession]);
    
    useEffect(() => {
        return () => {
            terminateActiveSession();
        };
    }, [terminateActiveSession]);

    const inSelectionMode = !selectedProduct;
    const showingPersonaSelection = Boolean(selectedProduct && !selectedPersona);
    const showingSimulation = Boolean(
        selectedProduct &&
        selectedPersona &&
        (isSimulating || transcripts.length > 0)
    );

    return (
        <main className="min-h-screen w-full flex flex-col items-center justify-center p-4 bg-gradient-to-br from-brand-dark to-slate-900 font-sans">
            {(inSelectionMode || showingPersonaSelection) && (
                <>
                    <h1 className="text-5xl font-extrabold text-center text-white mb-4">AI Sales Training Simulator</h1>
                    <p className="text-xl text-center text-brand-accent mb-8 max-w-3xl">Practice real-world sales conversations with an AI-powered customer. Select your product, choose a customer persona, and hone your pitch in a safe, interactive environment.</p>
                </>
            )}

            {inSelectionMode && (
                <ProductSelector onSelect={handleProductSelect} />
            )}

            {showingPersonaSelection && selectedProduct && (
                <>
                    <PersonaSelector product={selectedProduct} onSelect={startSimulation} />
                    <div className="mt-6 text-center">
                        <button
                            className="px-6 py-2 text-sm font-semibold text-brand-light underline decoration-brand-accent decoration-2 hover:text-white"
                            onClick={handleChangeProduct}
                        >
                            Choose a different product
                        </button>
                    </div>
                </>
            )}

            {showingSimulation && selectedProduct && selectedPersona && (
                <div className="w-full h-[90vh] max-h-[800px] flex flex-col">
                    <SimulationView
                        persona={selectedPersona}
                        product={selectedProduct}
                        status={status}
                        transcripts={transcripts}
                        onEnd={endSimulation}
                        isEnding={isEndingSimulation}
                        sessionEnded={sessionEnded}
                    />
                    {isSimulating && !sessionEnded && (
                        <>
                            <div className="flex justify-center mt-4 gap-4">
                                <button
                                    className={`px-8 py-3 ${micMuted ? 'bg-slate-600 hover:bg-slate-500' : 'bg-green-600 hover:bg-green-700'} text-white font-bold rounded-full transition-colors duration-300 ${!workletReady ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    onClick={() => setMicMuted((prev) => !prev)}
                                    disabled={!workletReady}
                                >
                                    <MicrophoneIcon className="w-6 h-6 mr-2 inline-block" /> {micMuted ? 'Unmute Microphone' : 'Mute Microphone'}
                                </button>
                            </div>
                            <p className="text-center text-sm text-slate-300 mt-2">Your microphone starts automatically when the AI is ready. Use the toggle to mute at any time.</p>
                        </>
                    )}
                </div>
            )}

            {selectedPersona && evaluationStatus !== 'idle' && (
                <EvaluationReport
                    evaluation={evaluationResult}
                    status={evaluationStatus}
                    error={evaluationError}
                    onRetry={retryEvaluation}
                    onRestart={startNewSimulation}
                    onDownload={handleDownloadReport}
                    persona={selectedPersona}
                    product={selectedProduct}
                />
            )}
        </main>
    );
}
