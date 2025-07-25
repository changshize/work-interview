# Real-Time Interview Assistant

A real-time speech translation and AI-powered answer generation tool for foreign language job interviews and academic admissions.

## Features

- **Real-time Speech Translation**: Capture and translate interviewer speech with <2s latency
- **AI-Powered Answer Generation**: Generate professional, contextually appropriate responses
- **Multi-language Support**: English, Chinese, and other common interview languages
- **Discreet UI**: Minimal overlay design for use during video interviews
- **Hybrid Architecture**: Cloud APIs with local model fallbacks

## Technical Stack

### Backend (Python)
- FastAPI for real-time API services
- WebSocket for real-time communication
- PyAudio for audio capture
- Multiple AI service integrations

### Frontend (React)
- Electron for cross-platform desktop app
- Real-time WebSocket client
- Minimal overlay UI design
- Tailwind CSS for styling

### AI Services
- **Speech-to-Text**: OpenAI Whisper API / Local Whisper
- **Translation**: Google Translate API / DeepL API
- **Answer Generation**: OpenAI GPT-4o-mini / Claude Haiku

## Performance Targets

- Audio capture: Real-time streaming
- Speech-to-text: <1.5 seconds
- Translation: <0.5 seconds
- AI generation: <2 seconds
- **Total pipeline: <3 seconds end-to-end**

## Quick Start

1. Clone the repository
2. Set up environment variables (see `.env.example`)
3. Install dependencies:
   ```bash
   # Backend
   cd backend && pip install -r requirements.txt
   
   # Frontend
   cd frontend && npm install
   ```
4. Run the application:
   ```bash
   # Start backend
   cd backend && python -m app.main
   
   # Start frontend
   cd frontend && npm start
   ```

## Configuration

Copy `.env.example` to `.env` and configure your API keys:

```env
# OpenAI
OPENAI_API_KEY=your_openai_key

# Google Cloud
GOOGLE_TRANSLATE_API_KEY=your_google_key

# DeepL (optional)
DEEPL_API_KEY=your_deepl_key

# Anthropic (optional)
ANTHROPIC_API_KEY=your_anthropic_key
```

## Architecture

The system uses a modular architecture with:
- Real-time audio processing pipeline
- Parallel translation and AI generation
- WebSocket-based real-time communication
- Fallback mechanisms for offline operation
- Error handling and recovery systems

## Privacy & Security

- Local audio processing when possible
- No persistent storage of conversations
- Encrypted API communications
- User consent for cloud processing

## License

MIT License - see LICENSE file for details
