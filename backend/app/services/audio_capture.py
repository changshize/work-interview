"""Audio capture service for real-time speech processing."""

import asyncio
try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import numpy as np
except ImportError:
    np = None
from typing import AsyncGenerator, Optional, Callable
from datetime import datetime
import logging
from ..config.settings import settings
from ..models.schemas import AudioChunk, AudioSettings

logger = logging.getLogger(__name__)


class AudioCaptureService:
    """Real-time audio capture service."""
    
    def __init__(self, audio_settings: Optional[AudioSettings] = None):
        self.settings = audio_settings or AudioSettings()
        self.audio = None
        self.stream = None
        self.is_recording = False
        self._callbacks = []
        
    async def initialize(self):
        """Initialize PyAudio."""
        if not pyaudio:
            logger.warning("PyAudio not available, audio capture disabled")
            return

        try:
            self.audio = pyaudio.PyAudio()
            logger.info("Audio capture service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            raise
    
    async def cleanup(self):
        """Clean up audio resources."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        logger.info("Audio capture service cleaned up")
    
    def add_callback(self, callback: Callable[[AudioChunk], None]):
        """Add callback for audio chunks."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[AudioChunk], None]):
        """Remove callback for audio chunks."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def start_recording(self) -> AsyncGenerator[AudioChunk, None]:
        """Start recording audio and yield chunks."""
        if self.is_recording:
            logger.warning("Recording already in progress")
            return
        
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.settings.channels,
                rate=self.settings.sample_rate,
                input=True,
                input_device_index=self.settings.device_index,
                frames_per_buffer=self.settings.chunk_size,
                stream_callback=None
            )
            
            self.is_recording = True
            logger.info("Started audio recording")
            
            while self.is_recording:
                try:
                    # Read audio data
                    audio_data = self.stream.read(
                        self.settings.chunk_size,
                        exception_on_overflow=False
                    )
                    
                    # Convert to numpy array (if available)
                    if np:
                        audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        duration = len(audio_array) / self.settings.sample_rate
                    else:
                        # Fallback calculation without numpy
                        duration = len(audio_data) / (self.settings.sample_rate * 2)  # 2 bytes per sample
                    
                    # Create audio chunk
                    chunk = AudioChunk(
                        data=audio_data,
                        timestamp=datetime.now(),
                        duration=duration,
                        sample_rate=self.settings.sample_rate
                    )
                    
                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback(chunk)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                    
                    yield chunk
                    
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error reading audio: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            raise
        finally:
            self.is_recording = False
            if self.stream:
                self.stream.stop_stream()
    
    def stop_recording(self):
        """Stop audio recording."""
        self.is_recording = False
        logger.info("Stopped audio recording")
    
    def get_audio_devices(self) -> list:
        """Get list of available audio input devices."""
        if not self.audio:
            return []
        
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'channels': device_info['maxInputChannels'],
                    'sample_rate': device_info['defaultSampleRate']
                })
        
        return devices
    
    def test_audio_level(self, duration: float = 1.0) -> float:
        """Test audio input level."""
        if not self.audio or not np:
            return 0.0

        try:
            test_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.settings.sample_rate,
                input=True,
                frames_per_buffer=self.settings.chunk_size
            )

            frames = int(self.settings.sample_rate * duration / self.settings.chunk_size)
            audio_data = []

            for _ in range(frames):
                data = test_stream.read(self.settings.chunk_size)
                audio_data.append(np.frombuffer(data, dtype=np.int16))

            test_stream.stop_stream()
            test_stream.close()

            # Calculate RMS level
            audio_array = np.concatenate(audio_data)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

            # Normalize to 0-1 range
            return min(rms / 32768.0, 1.0)

        except Exception as e:
            logger.error(f"Audio level test failed: {e}")
            return 0.0


class AudioBuffer:
    """Circular buffer for audio data."""

    def __init__(self, max_duration: float = 30.0, sample_rate: int = 16000):
        self.max_duration = max_duration
        self.sample_rate = sample_rate
        self.max_samples = int(max_duration * sample_rate)
        if np:
            self.buffer = np.zeros(self.max_samples, dtype=np.int16)
        else:
            self.buffer = [0] * self.max_samples  # Fallback to list
        self.write_pos = 0
        self.is_full = False
    
    def add_chunk(self, chunk: AudioChunk):
        """Add audio chunk to buffer."""
        if not np:
            return  # Skip if numpy not available

        audio_array = np.frombuffer(chunk.data, dtype=np.int16)
        chunk_size = len(audio_array)
        
        if chunk_size > self.max_samples:
            # Chunk is larger than buffer, take the last part
            audio_array = audio_array[-self.max_samples:]
            chunk_size = self.max_samples
        
        # Check if we need to wrap around
        if self.write_pos + chunk_size > self.max_samples:
            # Split the chunk
            first_part_size = self.max_samples - self.write_pos
            second_part_size = chunk_size - first_part_size
            
            self.buffer[self.write_pos:] = audio_array[:first_part_size]
            self.buffer[:second_part_size] = audio_array[first_part_size:]
            self.write_pos = second_part_size
        else:
            # Normal write
            self.buffer[self.write_pos:self.write_pos + chunk_size] = audio_array
            self.write_pos += chunk_size
        
        if self.write_pos >= self.max_samples:
            self.is_full = True
            self.write_pos = 0
    
    def get_audio_data(self, duration: Optional[float] = None):
        """Get audio data from buffer."""
        if not np:
            return []  # Return empty list if numpy not available

        if duration is None:
            if self.is_full:
                # Return full buffer in correct order
                return np.concatenate([
                    self.buffer[self.write_pos:],
                    self.buffer[:self.write_pos]
                ])
            else:
                # Return data up to write position
                return self.buffer[:self.write_pos]
        else:
            # Return specific duration
            samples = int(duration * self.sample_rate)
            samples = min(samples, self.max_samples)
            
            if self.is_full:
                start_pos = (self.write_pos - samples) % self.max_samples
                if start_pos + samples <= self.max_samples:
                    return self.buffer[start_pos:start_pos + samples]
                else:
                    return np.concatenate([
                        self.buffer[start_pos:],
                        self.buffer[:samples - (self.max_samples - start_pos)]
                    ])
            else:
                start_pos = max(0, self.write_pos - samples)
                return self.buffer[start_pos:self.write_pos]
