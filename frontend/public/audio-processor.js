class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.isListening = false;
    this.lastAudioTime = currentTime;
    this.silenceInterval = 1.0; // seconds
    this.silenceLength = 320; // 20ms at 16kHz

    // Listen for control messages from main thread
    this.port.onmessage = (event) => {
      if (event.data.type === 'setListening') {
        this.isListening = event.data.value;
        console.debug(`[AudioProcessor] Listening set to: ${this.isListening}`);
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    let sentAudio = false;
    if (input.length > 0 && this.isListening) {
      const channelData = input[0];
      // Check if input is not silence
      let hasNonZero = false;
      for (let i = 0; i < channelData.length; i++) {
        if (Math.abs(channelData[i]) > 1e-4) {
          hasNonZero = true;
          break;
        }
      }
      // Convert Float32Array to Int16Array for transmission
      const int16Data = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      if (hasNonZero) {
        this.port.postMessage(int16Data);
        this.lastAudioTime = currentTime;
        sentAudio = true;
      }
    }
    // If listening and no audio sent recently, send silence as keepalive
    if (this.isListening && (currentTime - this.lastAudioTime) > this.silenceInterval) {
      const silence = new Int16Array(this.silenceLength); // already zeroed
      this.port.postMessage(silence);
      this.lastAudioTime = currentTime;
    }
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);