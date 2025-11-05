class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.isListening = true;

    // Listen for control messages from main thread
    this.port.onmessage = (event) => {
      if (event.data.type === 'setListening') {
        this.isListening = event.data.value;
        console.log(`[AudioProcessor] Listening set to: ${this.isListening}`);
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input.length > 0 && this.isListening) {
      const channelData = input[0];

      // Convert Float32Array to Int16Array for transmission
      const int16Data = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      this.port.postMessage(int16Data);
    }
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);