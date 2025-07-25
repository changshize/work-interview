"""Main FastAPI application for real-time interview assistant."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import json
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .config.settings import settings, validate_api_keys, get_settings
from .models.schemas import (
    TranscriptionRequest, TranslationRequest, AnswerGenerationRequest,
    RealTimeMessage, HealthCheck, ServiceStatus, ConfigUpdate,
    AudioSettings, InterviewSession
)
from .services.speech_service import SpeechToTextService
from .services.translation_service import TranslationService
from .services.ai_service import AIAnswerService
from .services.audio_capture import AudioCaptureService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Real-Time Interview Assistant",
    description="AI-powered real-time speech translation and answer generation for interviews",
    version="1.0.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
stt_service: Optional[SpeechToTextService] = None
translation_service: Optional[TranslationService] = None
ai_service: Optional[AIAnswerService] = None
audio_service: Optional[AudioCaptureService] = None

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}
active_sessions: Dict[str, InterviewSession] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global stt_service, translation_service, ai_service, audio_service
    
    try:
        logger.info("Starting Real-Time Interview Assistant...")
        
        # Validate API keys
        validate_api_keys()
        
        # Initialize services
        stt_service = SpeechToTextService()
        translation_service = TranslationService()
        ai_service = AIAnswerService()
        audio_service = AudioCaptureService()
        
        await audio_service.initialize()
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down services...")
    
    if audio_service:
        await audio_service.cleanup()
    
    # Close all WebSocket connections
    for connection in active_connections.values():
        try:
            await connection.close()
        except:
            pass
    
    logger.info("Shutdown complete")


# Health check endpoint
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    services_status = {}
    
    # Check STT service
    try:
        if stt_service and stt_service.providers:
            services_status["speech_to_text"] = "healthy"
        else:
            services_status["speech_to_text"] = "unhealthy"
    except:
        services_status["speech_to_text"] = "unhealthy"
    
    # Check translation service
    try:
        if translation_service and translation_service.providers:
            services_status["translation"] = "healthy"
        else:
            services_status["translation"] = "unhealthy"
    except:
        services_status["translation"] = "unhealthy"
    
    # Check AI service
    try:
        if ai_service and ai_service.providers:
            services_status["ai_generation"] = "healthy"
        else:
            services_status["ai_generation"] = "unhealthy"
    except:
        services_status["ai_generation"] = "unhealthy"
    
    # Check audio service
    try:
        if audio_service:
            services_status["audio_capture"] = "healthy"
        else:
            services_status["audio_capture"] = "unhealthy"
    except:
        services_status["audio_capture"] = "unhealthy"
    
    overall_status = "healthy" if all(status == "healthy" for status in services_status.values()) else "degraded"
    
    return HealthCheck(
        status=overall_status,
        timestamp=datetime.now(),
        services=services_status,
        version="1.0.0"
    )


# Configuration endpoints
@app.post("/config/update")
async def update_config(config: ConfigUpdate):
    """Update application configuration."""
    try:
        # Update settings (in a real app, you'd persist these)
        if config.source_language:
            settings.default_source_language = config.source_language
        if config.target_language:
            settings.default_target_language = config.target_language
        if config.stt_provider:
            settings.stt_provider = config.stt_provider
        if config.translation_provider:
            settings.translation_provider = config.translation_provider
        if config.answer_style:
            settings.answer_style = config.answer_style
        
        return {"status": "success", "message": "Configuration updated"}
    
    except Exception as e:
        logger.error(f"Configuration update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config/current")
async def get_current_config():
    """Get current configuration."""
    return {
        "source_language": settings.default_source_language,
        "target_language": settings.default_target_language,
        "stt_provider": settings.stt_provider,
        "translation_provider": settings.translation_provider,
        "answer_style": settings.answer_style,
        "answer_max_length": settings.answer_max_length
    }


# Audio device endpoints
@app.get("/audio/devices")
async def get_audio_devices():
    """Get available audio input devices."""
    try:
        if not audio_service:
            raise HTTPException(status_code=503, detail="Audio service not available")
        
        devices = audio_service.get_audio_devices()
        return {"devices": devices}
    
    except Exception as e:
        logger.error(f"Failed to get audio devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/audio/test")
async def test_audio_level():
    """Test audio input level."""
    try:
        if not audio_service:
            raise HTTPException(status_code=503, detail="Audio service not available")
        
        level = audio_service.test_audio_level(duration=1.0)
        return {"level": level, "status": "good" if level > 0.1 else "low"}
    
    except Exception as e:
        logger.error(f"Audio test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Individual service endpoints for testing
@app.post("/transcribe")
async def transcribe_audio(request: TranscriptionRequest):
    """Transcribe audio to text."""
    try:
        if not stt_service:
            raise HTTPException(status_code=503, detail="Speech-to-text service not available")
        
        result = await stt_service.transcribe(request)
        return result
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate")
async def translate_text(request: TranslationRequest):
    """Translate text."""
    try:
        if not translation_service:
            raise HTTPException(status_code=503, detail="Translation service not available")
        
        result = await translation_service.translate(request)
        return result
    
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-answer")
async def generate_answer(request: AnswerGenerationRequest):
    """Generate AI answer for interview question."""
    try:
        if not ai_service:
            raise HTTPException(status_code=503, detail="AI service not available")
        
        result = await ai_service.generate_answer(request)
        return result
    
    except Exception as e:
        logger.error(f"Answer generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time processing
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time interview assistance."""
    await websocket.accept()
    active_connections[session_id] = websocket
    
    # Create new session
    session = InterviewSession(
        session_id=session_id,
        start_time=datetime.now(),
        source_language=settings.default_source_language,
        target_language=settings.default_target_language
    )
    active_sessions[session_id] = session
    
    logger.info(f"WebSocket connection established for session {session_id}")
    
    try:
        # Send welcome message
        await send_message(session_id, "status", {
            "message": "Connected to Real-Time Interview Assistant",
            "session_id": session_id,
            "capabilities": ["transcription", "translation", "answer_generation"]
        })
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await handle_websocket_message(session_id, message)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await send_error(session_id, "WebSocket error", str(e))
    finally:
        # Cleanup
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in active_sessions:
            del active_sessions[session_id]


async def handle_websocket_message(session_id: str, message: Dict):
    """Handle incoming WebSocket message."""
    message_type = message.get("type")
    data = message.get("data", {})
    
    try:
        if message_type == "audio_chunk":
            await process_audio_chunk(session_id, data)
        elif message_type == "config_update":
            await update_session_config(session_id, data)
        elif message_type == "ping":
            await send_message(session_id, "pong", {"timestamp": datetime.now().isoformat()})
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    except Exception as e:
        logger.error(f"Error handling message {message_type}: {e}")
        await send_error(session_id, f"Error processing {message_type}", str(e))


async def process_audio_chunk(session_id: str, data: Dict):
    """Process audio chunk through the full pipeline."""
    try:
        session = active_sessions.get(session_id)
        if not session:
            return
        
        audio_data = data.get("audio_data")
        if not audio_data:
            return
        
        # Step 1: Transcription
        transcription_request = TranscriptionRequest(
            audio_data=audio_data,
            language=session.source_language,
            provider=settings.stt_provider
        )
        
        transcription = await stt_service.transcribe(transcription_request)
        
        # Send transcription result
        await send_message(session_id, "transcription", {
            "text": transcription.text,
            "confidence": transcription.confidence,
            "language": transcription.language,
            "processing_time": transcription.processing_time
        })
        
        if not transcription.text.strip():
            return
        
        # Step 2: Translation (if needed)
        if session.source_language != session.target_language:
            translation_request = TranslationRequest(
                text=transcription.text,
                source_language=transcription.language,
                target_language=session.target_language,
                provider=settings.translation_provider
            )
            
            translation = await translation_service.translate(translation_request)
            
            # Send translation result
            await send_message(session_id, "translation", {
                "original_text": translation.original_text,
                "translated_text": translation.translated_text,
                "source_language": translation.source_language,
                "target_language": translation.target_language,
                "confidence": translation.confidence,
                "processing_time": translation.processing_time
            })
            
            question_text = translation.translated_text
        else:
            question_text = transcription.text
        
        # Step 3: Answer Generation
        answer_request = AnswerGenerationRequest(
            question=question_text,
            style=settings.answer_style,
            max_length=settings.answer_max_length,
            language=session.target_language,
            provider="openai"  # Default to OpenAI for now
        )
        
        answer = await ai_service.generate_answer(answer_request)
        
        # Send answer result
        await send_message(session_id, "answer", {
            "question": answer.question,
            "answer": answer.answer,
            "confidence": answer.confidence,
            "processing_time": answer.processing_time,
            "style": settings.answer_style
        })
    
    except Exception as e:
        logger.error(f"Pipeline processing error: {e}")
        await send_error(session_id, "Pipeline error", str(e))


async def update_session_config(session_id: str, config: Dict):
    """Update session configuration."""
    session = active_sessions.get(session_id)
    if not session:
        return
    
    if "source_language" in config:
        session.source_language = config["source_language"]
    if "target_language" in config:
        session.target_language = config["target_language"]
    
    await send_message(session_id, "config_updated", {
        "source_language": session.source_language,
        "target_language": session.target_language
    })


async def send_message(session_id: str, message_type: str, data: Dict):
    """Send message to WebSocket client."""
    if session_id not in active_connections:
        return
    
    message = RealTimeMessage(
        type=message_type,
        session_id=session_id,
        timestamp=datetime.now(),
        data=data
    )
    
    try:
        await active_connections[session_id].send_text(message.json())
    except Exception as e:
        logger.error(f"Failed to send message to {session_id}: {e}")


async def send_error(session_id: str, error: str, message: str):
    """Send error message to WebSocket client."""
    await send_message(session_id, "error", {
        "error": error,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
