/**
 * Audio capture and processing service
 */

class AudioService {
  constructor() {
    this.mediaRecorder = null;
    this.audioStream = null;
    this.isRecording = false;
    this.audioChunks = [];
    this.onAudioChunk = null;
    this.recordingInterval = null;
    this.chunkDuration = 2000; // 2 seconds
    this.sampleRate = 16000;
  }

  /**
   * Initialize audio service and request microphone permission
   */
  async initialize() {
    try {
      // Request microphone permission
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      console.log('Audio service initialized successfully');
      return true;
    } catch (error) {
      console.error('Failed to initialize audio service:', error);
      throw new Error('Microphone access denied or not available');
    }
  }

  /**
   * Start recording audio
   */
  async startRecording(onAudioChunk) {
    if (this.isRecording) {
      console.warn('Recording already in progress');
      return;
    }

    if (!this.audioStream) {
      await this.initialize();
    }

    this.onAudioChunk = onAudioChunk;
    this.audioChunks = [];

    try {
      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.audioStream, {
        mimeType: this.getSupportedMimeType(),
        audioBitsPerSecond: 128000
      });

      // Handle data available
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      // Handle recording stop
      this.mediaRecorder.onstop = () => {
        this.processAudioChunks();
      };

      // Start recording
      this.mediaRecorder.start();
      this.isRecording = true;

      // Set up interval to process chunks
      this.recordingInterval = setInterval(() => {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
          this.mediaRecorder.stop();
          this.mediaRecorder.start();
        }
      }, this.chunkDuration);

      console.log('Audio recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw error;
    }
  }

  /**
   * Stop recording audio
   */
  stopRecording() {
    if (!this.isRecording) {
      return;
    }

    this.isRecording = false;

    if (this.recordingInterval) {
      clearInterval(this.recordingInterval);
      this.recordingInterval = null;
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }

    console.log('Audio recording stopped');
  }

  /**
   * Process audio chunks and convert to base64
   */
  async processAudioChunks() {
    if (this.audioChunks.length === 0) {
      return;
    }

    try {
      // Combine chunks into a single blob
      const audioBlob = new Blob(this.audioChunks, { 
        type: this.getSupportedMimeType() 
      });

      // Convert to base64
      const base64Audio = await this.blobToBase64(audioBlob);

      // Clear chunks
      this.audioChunks = [];

      // Send to callback
      if (this.onAudioChunk) {
        this.onAudioChunk(base64Audio);
      }
    } catch (error) {
      console.error('Failed to process audio chunks:', error);
    }
  }

  /**
   * Convert blob to base64
   */
  blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1]; // Remove data:audio/... prefix
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * Get supported MIME type for recording
   */
  getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/wav'
    ];

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }

    return 'audio/webm'; // Fallback
  }

  /**
   * Test audio input level
   */
  async testAudioLevel(duration = 1000) {
    if (!this.audioStream) {
      await this.initialize();
    }

    return new Promise((resolve) => {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const microphone = audioContext.createMediaStreamSource(this.audioStream);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      microphone.connect(analyser);
      analyser.fftSize = 256;

      let maxLevel = 0;
      const startTime = Date.now();

      const checkLevel = () => {
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate RMS level
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sum / dataArray.length);
        const level = rms / 255; // Normalize to 0-1

        maxLevel = Math.max(maxLevel, level);

        if (Date.now() - startTime < duration) {
          requestAnimationFrame(checkLevel);
        } else {
          audioContext.close();
          resolve(maxLevel);
        }
      };

      checkLevel();
    });
  }

  /**
   * Get available audio input devices
   */
  async getAudioDevices() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter(device => device.kind === 'audioinput');
    } catch (error) {
      console.error('Failed to get audio devices:', error);
      return [];
    }
  }

  /**
   * Switch to a different audio input device
   */
  async switchAudioDevice(deviceId) {
    try {
      // Stop current stream
      if (this.audioStream) {
        this.audioStream.getTracks().forEach(track => track.stop());
      }

      // Get new stream with specified device
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: { exact: deviceId },
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      console.log('Switched to audio device:', deviceId);
      return true;
    } catch (error) {
      console.error('Failed to switch audio device:', error);
      throw error;
    }
  }

  /**
   * Cleanup audio resources
   */
  cleanup() {
    this.stopRecording();

    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
      this.audioStream = null;
    }

    this.mediaRecorder = null;
    this.onAudioChunk = null;
    this.audioChunks = [];

    console.log('Audio service cleaned up');
  }

  /**
   * Get current recording status
   */
  getStatus() {
    return {
      isRecording: this.isRecording,
      hasStream: !!this.audioStream,
      chunkDuration: this.chunkDuration,
      sampleRate: this.sampleRate
    };
  }

  /**
   * Set chunk duration for recording
   */
  setChunkDuration(duration) {
    this.chunkDuration = Math.max(1000, Math.min(10000, duration)); // 1-10 seconds
  }
}

// Create singleton instance
const audioService = new AudioService();

export default audioService;
