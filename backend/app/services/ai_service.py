"""AI-powered answer generation service."""

import asyncio
import time
from typing import Dict, Any, Optional, List
import logging
import json

# AI Service imports (with fallbacks for testing)
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

from ..config.settings import settings, get_model_config
from ..models.schemas import AnswerGenerationRequest, AnswerGenerationResponse

logger = logging.getLogger(__name__)


class AIAnswerService:
    """AI-powered answer generation service."""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
        self._load_prompts()
    
    def _initialize_providers(self):
        """Initialize available AI providers."""
        # OpenAI
        if settings.openai_api_key and openai:
            try:
                self.providers['openai'] = OpenAIProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # Anthropic Claude
        if settings.anthropic_api_key and anthropic:
            try:
                self.providers['anthropic'] = AnthropicProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")

        # Mock provider for testing
        if not self.providers:
            self.providers['mock'] = MockAIProvider()
            logger.info("No real AI providers available, using mock provider")

        logger.info(f"Initialized AI providers: {list(self.providers.keys())}")
    
    def _load_prompts(self):
        """Load prompt templates for different styles."""
        self.prompts = {
            'professional': {
                'system': """You are an expert interview coach helping someone prepare professional, concise answers for job interviews. 
                
Guidelines:
- Keep answers brief (1-2 sentences, max 150 words)
- Be professional and confident
- Focus on relevant skills and experience
- Use action verbs and specific examples when possible
- Avoid filler words and unnecessary details
- Make answers sound natural when spoken aloud""",
                
                'user': """Question: {question}
                
Context: {context}

Provide a brief, professional answer that would be appropriate for a job interview. The answer should be:
- Concise and direct
- Professional in tone
- Easy to speak aloud
- Relevant to the question asked"""
            },
            
            'academic': {
                'system': """You are helping someone prepare for academic interviews (graduate school, research positions, etc.).
                
Guidelines:
- Keep answers scholarly but accessible (1-2 sentences, max 150 words)
- Demonstrate intellectual curiosity and analytical thinking
- Reference relevant academic concepts when appropriate
- Show passion for the field of study
- Be humble but confident about achievements""",
                
                'user': """Question: {question}
                
Context: {context}

Provide a brief, academic answer suitable for a graduate school or research position interview."""
            },
            
            'casual': {
                'system': """You are helping someone prepare conversational, natural answers for informal interviews.
                
Guidelines:
- Keep answers natural and conversational (1-2 sentences, max 150 words)
- Use a friendly, approachable tone
- Be authentic and genuine
- Show personality while remaining professional
- Make it sound like natural speech""",
                
                'user': """Question: {question}
                
Context: {context}

Provide a brief, natural answer that sounds conversational but still professional."""
            }
        }
    
    async def generate_answer(self, request: AnswerGenerationRequest) -> AnswerGenerationResponse:
        """Generate AI answer for interview question."""
        provider = self.providers.get(request.provider)
        if not provider:
            raise ValueError(f"Provider {request.provider} not available")
        
        start_time = time.time()
        
        try:
            # Get appropriate prompt
            prompt_template = self.prompts.get(request.style, self.prompts['professional'])
            
            # Format prompt
            formatted_prompt = self._format_prompt(prompt_template, request)
            
            # Generate answer
            result = await provider.generate(formatted_prompt, request)
            processing_time = time.time() - start_time
            
            # Post-process answer
            processed_answer = self._post_process_answer(result['answer'], request)
            
            return AnswerGenerationResponse(
                question=request.question,
                answer=processed_answer,
                confidence=result.get('confidence', 0.9),
                processing_time=processing_time,
                provider=request.provider,
                metadata={
                    'style': request.style,
                    'language': request.language,
                    'original_length': len(result['answer']),
                    'processed_length': len(processed_answer)
                }
            )
        
        except Exception as e:
            logger.error(f"Answer generation failed with {request.provider}: {e}")
            # Try fallback provider
            return await self._try_fallback(request, start_time)
    
    def _format_prompt(self, prompt_template: Dict[str, str], request: AnswerGenerationRequest) -> Dict[str, str]:
        """Format prompt template with request data."""
        context = request.context or "This is a general interview question."
        
        return {
            'system': prompt_template['system'],
            'user': prompt_template['user'].format(
                question=request.question,
                context=context
            )
        }
    
    def _post_process_answer(self, answer: str, request: AnswerGenerationRequest) -> str:
        """Post-process generated answer."""
        # Remove extra whitespace
        answer = ' '.join(answer.split())
        
        # Ensure it's within length limit
        if len(answer.split()) > request.max_length:
            words = answer.split()[:request.max_length]
            answer = ' '.join(words)
            
            # Try to end at a sentence boundary
            if not answer.endswith('.'):
                last_period = answer.rfind('.')
                if last_period > len(answer) * 0.7:  # If period is in last 30%
                    answer = answer[:last_period + 1]
        
        # Ensure proper punctuation
        if not answer.endswith(('.', '!', '?')):
            answer += '.'
        
        return answer.strip()
    
    async def _try_fallback(self, request: AnswerGenerationRequest, start_time: float) -> AnswerGenerationResponse:
        """Try fallback providers if primary fails."""
        fallback_order = ['openai', 'anthropic']
        
        for provider_name in fallback_order:
            if provider_name == request.provider or provider_name not in self.providers:
                continue
            
            try:
                logger.info(f"Trying fallback AI provider: {provider_name}")
                provider = self.providers[provider_name]
                request.provider = provider_name
                
                prompt_template = self.prompts.get(request.style, self.prompts['professional'])
                formatted_prompt = self._format_prompt(prompt_template, request)
                
                result = await provider.generate(formatted_prompt, request)
                processing_time = time.time() - start_time
                
                processed_answer = self._post_process_answer(result['answer'], request)
                
                return AnswerGenerationResponse(
                    question=request.question,
                    answer=processed_answer,
                    confidence=result.get('confidence', 0.8),  # Lower confidence for fallback
                    processing_time=processing_time,
                    provider=provider_name,
                    metadata={'fallback': True, 'style': request.style}
                )
            
            except Exception as e:
                logger.error(f"Fallback AI provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All AI providers failed")


class OpenAIProvider:
    """OpenAI GPT provider."""
    
    def __init__(self):
        config = get_model_config('openai')
        self.client = openai.AsyncOpenAI(api_key=config['api_key'])
        self.model = config['model']
    
    async def generate(self, prompt: Dict[str, str], request: AnswerGenerationRequest) -> Dict[str, Any]:
        """Generate answer using OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt['system']},
                    {"role": "user", "content": prompt['user']}
                ],
                max_tokens=min(request.max_length * 2, 300),  # Allow some buffer
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                'answer': answer,
                'confidence': 0.9,
                'usage': response.usage.dict() if response.usage else {}
            }
        
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise


class AnthropicProvider:
    """Anthropic Claude provider."""
    
    def __init__(self):
        config = get_model_config('anthropic')
        self.client = anthropic.AsyncAnthropic(api_key=config['api_key'])
        self.model = config['model']
    
    async def generate(self, prompt: Dict[str, str], request: AnswerGenerationRequest) -> Dict[str, Any]:
        """Generate answer using Anthropic Claude."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=min(request.max_length * 2, 300),
                temperature=0.7,
                system=prompt['system'],
                messages=[
                    {"role": "user", "content": prompt['user']}
                ]
            )
            
            answer = response.content[0].text.strip()
            
            return {
                'answer': answer,
                'confidence': 0.9,
                'usage': response.usage.dict() if hasattr(response, 'usage') else {}
            }
        
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise


# Utility functions
def extract_question_type(question: str) -> str:
    """Extract the type of interview question."""
    question_lower = question.lower()
    
    if any(phrase in question_lower for phrase in ['tell me about yourself', 'introduce yourself']):
        return 'introduction'
    elif any(phrase in question_lower for phrase in ['why do you want', 'why are you interested']):
        return 'motivation'
    elif any(phrase in question_lower for phrase in ['strength', 'weakness']):
        return 'self_assessment'
    elif any(phrase in question_lower for phrase in ['experience', 'project', 'worked on']):
        return 'experience'
    elif any(phrase in question_lower for phrase in ['challenge', 'difficult', 'problem']):
        return 'problem_solving'
    elif any(phrase in question_lower for phrase in ['future', 'goal', 'plan']):
        return 'future_goals'
    else:
        return 'general'


def validate_answer_quality(answer: str, question: str) -> Dict[str, Any]:
    """Validate the quality of generated answer."""
    metrics = {
        'length_appropriate': 20 <= len(answer.split()) <= 150,
        'has_punctuation': answer.endswith(('.', '!', '?')),
        'not_too_repetitive': len(set(answer.split())) / len(answer.split()) > 0.7,
        'addresses_question': len(set(question.lower().split()) & set(answer.lower().split())) > 0
    }

    score = sum(metrics.values()) / len(metrics)

    return {
        'score': score,
        'metrics': metrics,
        'is_acceptable': score >= 0.75
    }


class MockAIProvider:
    """Mock AI provider for testing."""

    async def generate(self, prompt: Dict[str, str], request: AnswerGenerationRequest) -> Dict[str, Any]:
        """Mock answer generation for testing."""
        # Simulate processing time
        await asyncio.sleep(0.2)

        # Generate a mock answer based on the question
        question = request.question.lower()

        if 'tell me about yourself' in question or 'introduce yourself' in question:
            answer = "I am a dedicated professional with strong communication skills and a passion for continuous learning. I believe my experience and enthusiasm make me a great fit for this role."
        elif 'why do you want' in question:
            answer = "I am excited about this opportunity because it aligns perfectly with my career goals and allows me to contribute my skills while growing professionally."
        elif 'strength' in question:
            answer = "One of my key strengths is my ability to work collaboratively while maintaining attention to detail. I consistently deliver high-quality results under pressure."
        elif 'weakness' in question:
            answer = "I sometimes focus too much on perfecting details, but I've learned to balance thoroughness with meeting deadlines effectively."
        elif 'experience' in question:
            answer = "In my previous roles, I have successfully managed projects and collaborated with diverse teams to achieve challenging goals and deliver excellent results."
        else:
            answer = "That's an excellent question. Based on my experience and understanding of the role, I believe the key is to approach challenges systematically while maintaining clear communication with stakeholders."

        return {
            'answer': answer,
            'confidence': 0.85,
            'usage': {'mock': True}
        }
