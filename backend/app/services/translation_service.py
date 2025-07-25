"""Translation service with multiple provider support."""

import asyncio
import time
from typing import Dict, Any, Optional
import logging

# Translation service imports (with fallbacks for testing)
try:
    from google.cloud import translate_v2 as translate
except ImportError:
    translate = None

try:
    from deep_translator import GoogleTranslator, DeepLTranslator
except ImportError:
    GoogleTranslator = None
    DeepLTranslator = None

try:
    import googletrans
except ImportError:
    googletrans = None

from ..config.settings import settings, get_model_config
from ..models.schemas import TranslationRequest, TranslationResponse

logger = logging.getLogger(__name__)


class TranslationService:
    """Translation service with multiple providers."""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available translation providers."""
        # Google Translate API
        if settings.google_translate_api_key and translate:
            try:
                self.providers['google'] = GoogleTranslateProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize Google Translate: {e}")

        # DeepL API
        if settings.deepl_api_key and DeepLTranslator:
            try:
                self.providers['deepl'] = DeepLProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize DeepL: {e}")

        # Free Google Translate (fallback)
        if googletrans:
            try:
                self.providers['google_free'] = GoogleTranslateFreeProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize free Google Translate: {e}")

        # Mock provider for testing
        if not self.providers:
            self.providers['mock'] = MockTranslationProvider()
            logger.info("No real translation providers available, using mock provider")

        logger.info(f"Initialized translation providers: {list(self.providers.keys())}")
    
    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Translate text using specified provider."""
        provider = self.providers.get(request.provider)
        if not provider:
            raise ValueError(f"Provider {request.provider} not available")
        
        start_time = time.time()
        
        try:
            result = await provider.translate(request)
            processing_time = time.time() - start_time
            
            return TranslationResponse(
                original_text=request.text,
                translated_text=result['translated_text'],
                source_language=result.get('source_language', request.source_language),
                target_language=request.target_language,
                confidence=result.get('confidence', 0.9),
                processing_time=processing_time,
                provider=request.provider
            )
        
        except Exception as e:
            logger.error(f"Translation failed with {request.provider}: {e}")
            # Try fallback provider
            return await self._try_fallback(request, start_time)
    
    async def _try_fallback(self, request: TranslationRequest, start_time: float) -> TranslationResponse:
        """Try fallback providers if primary fails."""
        fallback_order = ['google_free', 'google', 'deepl']
        
        for provider_name in fallback_order:
            if provider_name == request.provider or provider_name not in self.providers:
                continue
            
            try:
                logger.info(f"Trying fallback translation provider: {provider_name}")
                provider = self.providers[provider_name]
                request.provider = provider_name
                
                result = await provider.translate(request)
                processing_time = time.time() - start_time
                
                return TranslationResponse(
                    original_text=request.text,
                    translated_text=result['translated_text'],
                    source_language=result.get('source_language', request.source_language),
                    target_language=request.target_language,
                    confidence=result.get('confidence', 0.8),  # Lower confidence for fallback
                    processing_time=processing_time,
                    provider=provider_name
                )
            
            except Exception as e:
                logger.error(f"Fallback translation provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All translation providers failed")
    
    def detect_language(self, text: str) -> str:
        """Detect language of input text."""
        try:
            # Use Google Translate for language detection
            if 'google' in self.providers:
                return self.providers['google'].detect_language(text)
            elif 'google_free' in self.providers:
                return self.providers['google_free'].detect_language(text)
            else:
                return 'auto'
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'auto'


class GoogleTranslateProvider:
    """Google Cloud Translate API provider."""
    
    def __init__(self):
        self.client = translate.Client()
    
    async def translate(self, request: TranslationRequest) -> Dict[str, Any]:
        """Translate using Google Cloud Translate API."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Detect source language if auto
            source_lang = request.source_language
            if source_lang == 'auto':
                detection = await loop.run_in_executor(
                    None,
                    self.client.detect_language,
                    request.text
                )
                source_lang = detection['language']
            
            # Perform translation
            result = await loop.run_in_executor(
                None,
                self.client.translate,
                request.text,
                target_language=request.target_language,
                source_language=source_lang if source_lang != 'auto' else None
            )
            
            return {
                'translated_text': result['translatedText'],
                'source_language': result.get('detectedSourceLanguage', source_lang),
                'confidence': 0.95
            }
        
        except Exception as e:
            logger.error(f"Google Translate API error: {e}")
            raise
    
    def detect_language(self, text: str) -> str:
        """Detect language using Google Translate API."""
        try:
            result = self.client.detect_language(text)
            return result['language']
        except:
            return 'auto'


class DeepLProvider:
    """DeepL API provider."""
    
    def __init__(self):
        self.api_key = settings.deepl_api_key
    
    async def translate(self, request: TranslationRequest) -> Dict[str, Any]:
        """Translate using DeepL API."""
        try:
            # Map language codes for DeepL
            target_lang = self._map_language_code(request.target_language)
            source_lang = self._map_language_code(request.source_language) if request.source_language != 'auto' else None
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            translator = DeepLTranslator(api_key=self.api_key, source=source_lang, target=target_lang)
            
            result = await loop.run_in_executor(
                None,
                translator.translate,
                request.text
            )
            
            return {
                'translated_text': result,
                'source_language': request.source_language,
                'confidence': 0.92
            }
        
        except Exception as e:
            logger.error(f"DeepL API error: {e}")
            raise
    
    def _map_language_code(self, lang_code: str) -> str:
        """Map language codes to DeepL format."""
        mapping = {
            'en': 'EN',
            'zh': 'ZH',
            'zh-cn': 'ZH',
            'zh-tw': 'ZH',
            'ja': 'JA',
            'ko': 'KO',
            'fr': 'FR',
            'de': 'DE',
            'es': 'ES',
            'it': 'IT',
            'pt': 'PT',
            'ru': 'RU'
        }
        return mapping.get(lang_code.lower(), lang_code.upper())


class GoogleTranslateFreeProvider:
    """Free Google Translate provider (fallback)."""
    
    def __init__(self):
        self.translator = googletrans.Translator()
    
    async def translate(self, request: TranslationRequest) -> Dict[str, Any]:
        """Translate using free Google Translate."""
        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            
            result = await loop.run_in_executor(
                None,
                self.translator.translate,
                request.text,
                dest=request.target_language,
                src=request.source_language if request.source_language != 'auto' else 'auto'
            )
            
            return {
                'translated_text': result.text,
                'source_language': result.src,
                'confidence': 0.85
            }
        
        except Exception as e:
            logger.error(f"Free Google Translate error: {e}")
            raise
    
    def detect_language(self, text: str) -> str:
        """Detect language using free Google Translate."""
        try:
            result = self.translator.detect(text)
            return result.lang
        except:
            return 'auto'


# Utility functions
def normalize_language_code(lang_code: str) -> str:
    """Normalize language code to standard format."""
    mapping = {
        'chinese': 'zh',
        'english': 'en',
        'japanese': 'ja',
        'korean': 'ko',
        'french': 'fr',
        'german': 'de',
        'spanish': 'es',
        'italian': 'it',
        'portuguese': 'pt',
        'russian': 'ru'
    }
    
    normalized = lang_code.lower().strip()
    return mapping.get(normalized, normalized)


def is_translation_needed(source_lang: str, target_lang: str) -> bool:
    """Check if translation is needed."""
    if source_lang == target_lang:
        return False

    # Handle language variants
    source_base = source_lang.split('-')[0]
    target_base = target_lang.split('-')[0]

    return source_base != target_base


class MockTranslationProvider:
    """Mock translation provider for testing."""

    async def translate(self, request: TranslationRequest) -> Dict[str, Any]:
        """Mock translation for testing."""
        # Simulate processing time
        await asyncio.sleep(0.1)

        # Simple mock translation
        if request.target_language == 'zh':
            translated = f"[中文翻译] {request.text}"
        elif request.target_language == 'en':
            translated = f"[English Translation] {request.text}"
        else:
            translated = f"[{request.target_language.upper()} Translation] {request.text}"

        return {
            'translated_text': translated,
            'source_language': request.source_language,
            'confidence': 0.90
        }

    def detect_language(self, text: str) -> str:
        """Mock language detection."""
        return 'en'  # Default to English
