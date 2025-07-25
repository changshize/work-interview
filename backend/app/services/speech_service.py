"""Speech-to-text service with multiple provider support."""

import asyncio
import base64
import io
import time
from typing import Optional, Dict, Any
import logging

# AI Service imports (with fallbacks for testing)
try:
    import openai
except ImportError:
    openai = None

try:
    import whisper
except ImportError:
    whisper = None

try:
    from google.cloud import speech
except ImportError:
    speech = None

from ..config.settings import settings, get_model_config
from ..models.schemas import TranscriptionRequest, TranscriptionResponse

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """Speech-to-text service with multiple providers."""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available STT providers."""
        # OpenAI Whisper API
        if settings.openai_api_key and openai:
            try:
                self.providers['openai'] = OpenAISTTProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI STT: {e}")

        # Google Speech-to-Text
        if settings.google_speech_api_key and speech:
            try:
                self.providers['google'] = GoogleSTTProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize Google STT: {e}")

        # Local Whisper
        if whisper:
            try:
                self.providers['local'] = LocalWhisperProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize Local Whisper: {e}")

        # Mock provider for testing
        if not self.providers:
            self.providers['mock'] = MockSTTProvider()
            logger.info("No real STT providers available, using mock provider")

        logger.info(f"Initialized STT providers: {list(self.providers.keys())}")
    
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse:
        """Transcribe audio using specified provider."""
        provider = self.providers.get(request.provider)
        if not provider:
            raise ValueError(f"Provider {request.provider} not available")
        
        start_time = time.time()
        
        try:
            result = await provider.transcribe(request)
            processing_time = time.time() - start_time
            
            return TranscriptionResponse(
                text=result['text'],
                confidence=result.get('confidence', 0.9),
                language=result.get('language', request.language),
                processing_time=processing_time,
                provider=request.provider
            )
        
        except Exception as e:
            logger.error(f"Transcription failed with {request.provider}: {e}")
            # Try fallback provider
            return await self._try_fallback(request, start_time)
    
    async def _try_fallback(self, request: TranscriptionRequest, start_time: float) -> TranscriptionResponse:
        """Try fallback providers if primary fails."""
        fallback_order = ['local', 'openai', 'google']
        
        for provider_name in fallback_order:
            if provider_name == request.provider or provider_name not in self.providers:
                continue
            
            try:
                logger.info(f"Trying fallback provider: {provider_name}")
                provider = self.providers[provider_name]
                request.provider = provider_name
                
                result = await provider.transcribe(request)
                processing_time = time.time() - start_time
                
                return TranscriptionResponse(
                    text=result['text'],
                    confidence=result.get('confidence', 0.8),  # Lower confidence for fallback
                    language=result.get('language', request.language),
                    processing_time=processing_time,
                    provider=provider_name
                )
            
            except Exception as e:
                logger.error(f"Fallback provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All STT providers failed")


class OpenAISTTProvider:
    """OpenAI Whisper API provider."""
    
    def __init__(self):
        config = get_model_config('openai')
        self.client = openai.AsyncOpenAI(api_key=config['api_key'])
    
    async def transcribe(self, request: TranscriptionRequest) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper API."""
        # Decode base64 audio
        audio_data = base64.b64decode(request.audio_data)
        
        # Create file-like object
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"
        
        try:
            response = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=request.language if request.language != "auto" else None,
                response_format="verbose_json"
            )
            
            return {
                'text': response.text,
                'confidence': 0.9,  # OpenAI doesn't provide confidence scores
                'language': response.language
            }
        
        except Exception as e:
            logger.error(f"OpenAI STT error: {e}")
            raise


class GoogleSTTProvider:
    """Google Speech-to-Text provider."""
    
    def __init__(self):
        self.client = speech.SpeechClient()
    
    async def transcribe(self, request: TranscriptionRequest) -> Dict[str, Any]:
        """Transcribe using Google Speech-to-Text."""
        # Decode base64 audio
        audio_data = base64.b64decode(request.audio_data)
        
        # Configure recognition
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=request.language if request.language != "auto" else "en-US",
            enable_automatic_punctuation=True,
            model="latest_long"
        )
        
        audio = speech.RecognitionAudio(content=audio_data)
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                self.client.recognize,
                config,
                audio
            )
            
            if not response.results:
                return {'text': '', 'confidence': 0.0, 'language': request.language}
            
            result = response.results[0]
            alternative = result.alternatives[0]
            
            return {
                'text': alternative.transcript,
                'confidence': alternative.confidence,
                'language': request.language
            }
        
        except Exception as e:
            logger.error(f"Google STT error: {e}")
            raise


class LocalWhisperProvider:
    """Local Whisper model provider."""
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load local Whisper model."""
        try:
            model_name = settings.local_whisper_model
            logger.info(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name)
            logger.info("Local Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
    
    async def transcribe(self, request: TranscriptionRequest) -> Dict[str, Any]:
        """Transcribe using local Whisper model."""
        if not self.model:
            raise Exception("Local Whisper model not available")
        
        # Decode base64 audio
        audio_data = base64.b64decode(request.audio_data)
        
        # Save to temporary file
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        try:
            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.model.transcribe,
                temp_path,
                {"language": request.language if request.language != "auto" else None}
            )
            
            return {
                'text': result['text'],
                'confidence': 0.85,  # Whisper doesn't provide confidence scores
                'language': result.get('language', request.language)
            }
        
        except Exception as e:
            logger.error(f"Local Whisper error: {e}")
            raise
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass


# Utility functions
def audio_to_base64(audio_data: bytes) -> str:
    """Convert audio bytes to base64 string."""
    return base64.b64encode(audio_data).decode('utf-8')


def validate_audio_format(audio_data: bytes) -> bool:
    """Validate audio format and quality."""
    try:
        # Basic validation - check if it's not empty and has reasonable size
        if len(audio_data) < 1000:  # Too short
            return False
        if len(audio_data) > 10 * 1024 * 1024:  # Too large (>10MB)
            return False
        return True
    except:
        return False


class MockSTTProvider:
    """Mock STT provider for testing."""

    async def transcribe(self, request: TranscriptionRequest) -> Dict[str, Any]:
        """Mock transcription for testing."""
        # Simulate processing time
        await asyncio.sleep(0.1)

        return {
            'text': 'This is a mock transcription for testing purposes.',
            'confidence': 0.95,
            'language': request.language if request.language != 'auto' else 'en'
        }
