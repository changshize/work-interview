"""Application configuration settings."""

import os
import logging
from typing import Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    from pydantic import BaseSettings, Field

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    google_translate_api_key: Optional[str] = Field(None, env="GOOGLE_TRANSLATE_API_KEY")
    google_speech_api_key: Optional[str] = Field(None, env="GOOGLE_SPEECH_API_KEY")
    deepl_api_key: Optional[str] = Field(None, env="DEEPL_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    
    # Model Configuration
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")
    anthropic_model: str = Field("claude-3-haiku-20240307", env="ANTHROPIC_MODEL")
    local_whisper_model: str = Field("small", env="LOCAL_WHISPER_MODEL")
    
    # Application Settings
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    host: str = Field("localhost", env="HOST")
    port: int = Field(8000, env="PORT")
    
    # Audio Configuration
    audio_sample_rate: int = Field(16000, env="AUDIO_SAMPLE_RATE")
    audio_chunk_size: int = Field(1024, env="AUDIO_CHUNK_SIZE")
    max_audio_duration: int = Field(30, env="MAX_AUDIO_DURATION")
    
    # Translation Settings
    default_source_language: str = Field("auto", env="DEFAULT_SOURCE_LANGUAGE")
    default_target_language: str = Field("en", env="DEFAULT_TARGET_LANGUAGE")
    translation_provider: str = Field("google", env="TRANSLATION_PROVIDER")
    
    # Speech-to-Text Settings
    stt_provider: str = Field("openai", env="STT_PROVIDER")
    
    # Answer Generation Settings
    answer_max_length: int = Field(150, env="ANSWER_MAX_LENGTH")
    answer_style: str = Field("professional", env="ANSWER_STYLE")
    answer_language: str = Field("en", env="ANSWER_LANGUAGE")
    
    # Performance Settings
    enable_caching: bool = Field(True, env="ENABLE_CACHING")
    cache_ttl: int = Field(3600, env="CACHE_TTL")
    max_concurrent_requests: int = Field(5, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(10, env="REQUEST_TIMEOUT")
    
    # Privacy Settings
    store_audio: bool = Field(False, env="STORE_AUDIO")
    store_transcripts: bool = Field(False, env="STORE_TRANSCRIPTS")
    enable_analytics: bool = Field(False, env="ENABLE_ANALYTICS")
    
    class Config:
        env_file = [".env", "../.env", "../../.env"]  # Try multiple paths
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


# Validation functions
def validate_api_keys():
    """Validate that required API keys are present."""
    # Skip validation in debug mode or if using test/mock providers
    if (settings.debug or
        settings.openai_api_key == "test_key" or
        settings.stt_provider in ["mock", "local"] or
        settings.translation_provider == "mock"):
        logger.info("Skipping API key validation in debug/test mode")
        return

    errors = []

    if not settings.openai_api_key and settings.stt_provider == "openai":
        errors.append("OpenAI API key required for OpenAI STT provider")

    if not settings.google_translate_api_key and settings.translation_provider == "google":
        errors.append("Google Translate API key required for Google translation provider")

    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")


def get_model_config(provider: str) -> dict:
    """Get model configuration for a specific provider."""
    configs = {
        "openai": {
            "api_key": settings.openai_api_key,
            "model": settings.openai_model,
            "timeout": settings.request_timeout
        },
        "anthropic": {
            "api_key": settings.anthropic_api_key,
            "model": settings.anthropic_model,
            "timeout": settings.request_timeout
        },
        "google": {
            "api_key": settings.google_translate_api_key,
            "timeout": settings.request_timeout
        }
    }
    
    return configs.get(provider, {})
