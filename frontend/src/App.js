import React, { useState, useEffect, useCallback } from 'react';
import { Mic, MicOff, Settings, Minimize2, Volume2, Languages, Brain } from 'lucide-react';
import toast, { Toaster } from 'react-hot-toast';
import webSocketService from './services/WebSocketService';
import audioService from './services/AudioService';
import './App.css';

function App() {
  // State management
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [currentTranscription, setCurrentTranscription] = useState('');
  const [currentTranslation, setCurrentTranslation] = useState('');
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [config, setConfig] = useState({
    sourceLanguage: 'auto',
    targetLanguage: 'en',
    answerStyle: 'professional'
  });
  const [showSettings, setShowSettings] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [processingTimes, setProcessingTimes] = useState({
    transcription: 0,
    translation: 0,
    answer: 0
  });

  // Initialize services
  useEffect(() => {
    const initializeServices = async () => {
      try {
        // Initialize audio service
        await audioService.initialize();
        
        // Connect to WebSocket
        await webSocketService.connect();
        
        toast.success('Connected to Interview Assistant');
      } catch (error) {
        console.error('Initialization failed:', error);
        toast.error('Failed to initialize services');
      }
    };

    initializeServices();

    // Cleanup on unmount
    return () => {
      audioService.cleanup();
      webSocketService.disconnect();
    };
  }, []);

  // WebSocket event handlers
  useEffect(() => {
    const handleConnected = () => {
      setIsConnected(true);
    };

    const handleDisconnected = () => {
      setIsConnected(false);
      setIsRecording(false);
    };

    const handleTranscription = (data) => {
      setCurrentTranscription(data.text);
      setProcessingTimes(prev => ({ ...prev, transcription: data.processing_time }));
      setIsLoading(true);
    };

    const handleTranslation = (data) => {
      setCurrentTranslation(data.translated_text);
      setProcessingTimes(prev => ({ ...prev, translation: data.processing_time }));
    };

    const handleAnswer = (data) => {
      setCurrentAnswer(data.answer);
      setProcessingTimes(prev => ({ ...prev, answer: data.processing_time }));
      setIsLoading(false);
    };

    const handleError = (data) => {
      console.error('WebSocket error:', data);
      toast.error(`Error: ${data.message}`);
      setIsLoading(false);
    };

    const handleConfigUpdated = (data) => {
      setConfig(prev => ({ ...prev, ...data }));
      toast.success('Configuration updated');
    };

    // Register event listeners
    webSocketService.on('connected', handleConnected);
    webSocketService.on('disconnected', handleDisconnected);
    webSocketService.on('transcription', handleTranscription);
    webSocketService.on('translation', handleTranslation);
    webSocketService.on('answer', handleAnswer);
    webSocketService.on('error', handleError);
    webSocketService.on('config_updated', handleConfigUpdated);

    // Cleanup listeners
    return () => {
      webSocketService.off('connected', handleConnected);
      webSocketService.off('disconnected', handleDisconnected);
      webSocketService.off('transcription', handleTranscription);
      webSocketService.off('translation', handleTranslation);
      webSocketService.off('answer', handleAnswer);
      webSocketService.off('error', handleError);
      webSocketService.off('config_updated', handleConfigUpdated);
    };
  }, []);

  // Audio chunk handler
  const handleAudioChunk = useCallback((audioData) => {
    if (isConnected) {
      webSocketService.sendAudioChunk(audioData);
    }
  }, [isConnected]);

  // Start/stop recording
  const toggleRecording = async () => {
    if (!isConnected) {
      toast.error('Not connected to server');
      return;
    }

    try {
      if (isRecording) {
        audioService.stopRecording();
        setIsRecording(false);
        toast.success('Recording stopped');
      } else {
        await audioService.startRecording(handleAudioChunk);
        setIsRecording(true);
        toast.success('Recording started');
        
        // Clear previous results
        setCurrentTranscription('');
        setCurrentTranslation('');
        setCurrentAnswer('');
      }
    } catch (error) {
      console.error('Recording toggle failed:', error);
      toast.error('Failed to toggle recording');
    }
  };

  // Update configuration
  const updateConfig = (newConfig) => {
    const updatedConfig = { ...config, ...newConfig };
    setConfig(updatedConfig);
    webSocketService.updateConfig(updatedConfig);
  };

  // Test audio level
  const testAudio = async () => {
    try {
      const level = await audioService.testAudioLevel(1000);
      setAudioLevel(level);
      
      if (level > 0.1) {
        toast.success(`Audio level: ${Math.round(level * 100)}%`);
      } else {
        toast.error('Audio level too low');
      }
    } catch (error) {
      toast.error('Audio test failed');
    }
  };

  // Clear results
  const clearResults = () => {
    setCurrentTranscription('');
    setCurrentTranslation('');
    setCurrentAnswer('');
    setIsLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <Toaster 
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#374151',
            color: '#fff',
          },
        }}
      />
      
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Interview Assistant</h1>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1 hover:bg-gray-700 rounded"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="bg-gray-800 border-b border-gray-700 p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Source Language</label>
              <select
                value={config.sourceLanguage}
                onChange={(e) => updateConfig({ sourceLanguage: e.target.value })}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm"
              >
                <option value="auto">Auto Detect</option>
                <option value="en">English</option>
                <option value="zh">Chinese</option>
                <option value="ja">Japanese</option>
                <option value="ko">Korean</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="es">Spanish</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Target Language</label>
              <select
                value={config.targetLanguage}
                onChange={(e) => updateConfig({ targetLanguage: e.target.value })}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm"
              >
                <option value="en">English</option>
                <option value="zh">Chinese</option>
                <option value="ja">Japanese</option>
                <option value="ko">Korean</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="es">Spanish</option>
              </select>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Answer Style</label>
            <select
              value={config.answerStyle}
              onChange={(e) => updateConfig({ answerStyle: e.target.value })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm"
            >
              <option value="professional">Professional</option>
              <option value="academic">Academic</option>
              <option value="casual">Casual</option>
            </select>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={testAudio}
              className="flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
            >
              <Volume2 size={14} />
              <span>Test Audio</span>
            </button>
            <button
              onClick={clearResults}
              className="px-3 py-1 bg-gray-600 hover:bg-gray-700 rounded text-sm"
            >
              Clear Results
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="p-4 space-y-4">
        {/* Recording Controls */}
        <div className="text-center">
          <button
            onClick={toggleRecording}
            disabled={!isConnected}
            className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${
              isRecording
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600'
            }`}
          >
            {isRecording ? <MicOff size={24} /> : <Mic size={24} />}
          </button>
          <p className="mt-2 text-sm text-gray-400">
            {isRecording ? 'Recording...' : 'Click to start recording'}
          </p>
        </div>

        {/* Processing Status */}
        {isLoading && (
          <div className="text-center">
            <div className="inline-flex items-center space-x-2 text-blue-400">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400"></div>
              <span className="text-sm">Processing...</span>
            </div>
          </div>
        )}

        {/* Results */}
        <div className="space-y-4">
          {/* Transcription */}
          {currentTranscription && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Mic size={16} className="text-blue-400" />
                <span className="text-sm font-medium text-blue-400">Transcription</span>
                {processingTimes.transcription > 0 && (
                  <span className="text-xs text-gray-500">
                    ({processingTimes.transcription.toFixed(2)}s)
                  </span>
                )}
              </div>
              <p className="text-gray-200">{currentTranscription}</p>
            </div>
          )}

          {/* Translation */}
          {currentTranslation && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Languages size={16} className="text-green-400" />
                <span className="text-sm font-medium text-green-400">Translation</span>
                {processingTimes.translation > 0 && (
                  <span className="text-xs text-gray-500">
                    ({processingTimes.translation.toFixed(2)}s)
                  </span>
                )}
              </div>
              <p className="text-gray-200">{currentTranslation}</p>
            </div>
          )}

          {/* AI Answer */}
          {currentAnswer && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Brain size={16} className="text-purple-400" />
                <span className="text-sm font-medium text-purple-400">Suggested Answer</span>
                {processingTimes.answer > 0 && (
                  <span className="text-xs text-gray-500">
                    ({processingTimes.answer.toFixed(2)}s)
                  </span>
                )}
              </div>
              <p className="text-gray-200 leading-relaxed">{currentAnswer}</p>
            </div>
          )}
        </div>

        {/* Performance Stats */}
        {(processingTimes.transcription > 0 || processingTimes.translation > 0 || processingTimes.answer > 0) && (
          <div className="bg-gray-800 rounded-lg p-3">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Performance</h3>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="text-center">
                <div className="text-blue-400">STT</div>
                <div>{processingTimes.transcription.toFixed(2)}s</div>
              </div>
              <div className="text-center">
                <div className="text-green-400">Translation</div>
                <div>{processingTimes.translation.toFixed(2)}s</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400">AI Answer</div>
                <div>{processingTimes.answer.toFixed(2)}s</div>
              </div>
            </div>
            <div className="mt-2 text-center text-gray-500">
              Total: {(processingTimes.transcription + processingTimes.translation + processingTimes.answer).toFixed(2)}s
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
