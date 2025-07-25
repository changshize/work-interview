"""Pydantic models for API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AudioChunk(BaseModel):
    """Audio chunk data for processing."""
    data: bytes
    timestamp: datetime
    duration: float
    sample_rate: int = 16000


class TranscriptionRequest(BaseModel):
    """Request for speech-to-text transcription."""
    audio_data: str  # Base64 encoded audio
    language: Optional[str] = "auto"
    provider: str = "openai"


class TranscriptionResponse(BaseModel):
    """Response from speech-to-text service."""
    text: str
    confidence: float
    language: str
    processing_time: float
    provider: str


class TranslationRequest(BaseModel):
    """Request for text translation."""
    text: str
    source_language: str = "auto"
    target_language: str = "en"
    provider: str = "google"


class TranslationResponse(BaseModel):
    """Response from translation service."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    processing_time: float
    provider: str


class AnswerGenerationRequest(BaseModel):
    """Request for AI answer generation."""
    question: str
    context: Optional[str] = None
    style: str = "professional"
    max_length: int = 150
    language: str = "en"
    provider: str = "openai"


class AnswerGenerationResponse(BaseModel):
    """Response from AI answer generation."""
    question: str
    answer: str
    confidence: float
    processing_time: float
    provider: str
    metadata: Dict[str, Any] = {}


class InterviewSession(BaseModel):
    """Interview session data."""
    session_id: str
    start_time: datetime
    source_language: str
    target_language: str
    is_active: bool = True


class RealTimeMessage(BaseModel):
    """Real-time WebSocket message."""
    type: str  # transcription, translation, answer, error, status
    session_id: str
    timestamp: datetime
    data: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    timestamp: datetime
    session_id: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    services: Dict[str, str]  # service_name -> status
    version: str


class ServiceStatus(BaseModel):
    """Individual service status."""
    name: str
    status: str  # healthy, degraded, unhealthy
    response_time: Optional[float] = None
    last_check: datetime
    error: Optional[str] = None


class PipelineResult(BaseModel):
    """Complete pipeline processing result."""
    session_id: str
    original_audio_duration: float
    transcription: TranscriptionResponse
    translation: TranslationResponse
    answer: AnswerGenerationResponse
    total_processing_time: float
    timestamp: datetime


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    stt_provider: Optional[str] = None
    translation_provider: Optional[str] = None
    answer_provider: Optional[str] = None
    answer_style: Optional[str] = None


class AudioSettings(BaseModel):
    """Audio capture settings."""
    sample_rate: int = 16000
    chunk_size: int = 1024
    channels: int = 1
    format: str = "int16"
    device_index: Optional[int] = None
