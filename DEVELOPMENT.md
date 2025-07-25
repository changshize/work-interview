# Development Guide

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys for AI services (see `.env.example`)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your API keys
python -m app.main
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

### Docker Setup
```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up --build
```

## Architecture Overview

### Backend (Python/FastAPI)
- **FastAPI**: Web framework with WebSocket support
- **Services**: Modular design for STT, Translation, and AI
- **Real-time**: WebSocket-based communication
- **Fallbacks**: Multiple provider support with automatic fallback

### Frontend (React/Electron)
- **React**: Modern UI with hooks and state management
- **Electron**: Cross-platform desktop application
- **WebSocket**: Real-time communication with backend
- **Audio**: Browser-based audio capture and processing

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Configuration
- `POST /config/update` - Update configuration
- `GET /config/current` - Get current configuration

### Audio
- `GET /audio/devices` - List audio input devices
- `POST /audio/test` - Test audio input level

### Individual Services (for testing)
- `POST /transcribe` - Speech-to-text
- `POST /translate` - Text translation
- `POST /generate-answer` - AI answer generation

### WebSocket
- `WS /ws/{session_id}` - Real-time processing pipeline

## WebSocket Message Types

### Client to Server
```json
{
  "type": "audio_chunk",
  "data": {
    "audio_data": "base64_encoded_audio",
    "timestamp": 1234567890
  }
}
```

```json
{
  "type": "config_update",
  "data": {
    "source_language": "en",
    "target_language": "zh"
  }
}
```

### Server to Client
```json
{
  "type": "transcription",
  "session_id": "session_123",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "text": "Hello world",
    "confidence": 0.95,
    "language": "en",
    "processing_time": 1.2
  }
}
```

## Performance Optimization

### Latency Targets
- Audio capture: Real-time streaming
- Speech-to-text: <1.5 seconds
- Translation: <0.5 seconds
- AI generation: <2 seconds
- **Total pipeline: <3 seconds**

### Optimization Strategies
1. **Parallel Processing**: Run translation and AI generation in parallel
2. **Chunked Audio**: Process 2-second audio chunks
3. **Connection Pooling**: Reuse HTTP connections
4. **Local Fallbacks**: Use local models when APIs fail
5. **Caching**: Cache common translations and responses

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Integration Tests
```bash
# Start services
docker-compose up -d

# Run integration tests
python tests/integration_test.py
```

## Deployment

### Production Environment Variables
```env
# Required
OPENAI_API_KEY=your_key
GOOGLE_TRANSLATE_API_KEY=your_key

# Optional but recommended
DEEPL_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Performance
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=15
ENABLE_CACHING=true

# Security
DEBUG=false
LOG_LEVEL=INFO
```

### Docker Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Electron Distribution
```bash
cd frontend
npm run build-electron
```

## Troubleshooting

### Common Issues

1. **Audio not working**
   - Check microphone permissions
   - Test with `/audio/test` endpoint
   - Verify browser audio support

2. **High latency**
   - Check network connection
   - Monitor API response times
   - Consider switching to local models

3. **API errors**
   - Verify API keys in `.env`
   - Check API quotas and limits
   - Review logs for specific errors

4. **WebSocket disconnections**
   - Check network stability
   - Monitor server logs
   - Verify firewall settings

### Debug Mode
```bash
# Backend
DEBUG=true python -m app.main

# Frontend
REACT_APP_DEBUG=true npm start
```

### Logging
- Backend logs: Console output with configurable levels
- Frontend logs: Browser console
- WebSocket messages: Debug mode shows all messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

### Code Style
- Backend: Black formatter, flake8 linting
- Frontend: ESLint, Prettier
- Commit messages: Conventional commits format

### Performance Testing
```bash
# Load test WebSocket connections
python scripts/load_test.py

# Measure latency
python scripts/latency_test.py
```
