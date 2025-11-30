import requests
import json
import os
from typing import Dict, List, Optional
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_BASE_URL', os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
        self.model = getattr(settings, 'OLLAMA_MODEL', os.getenv('OLLAMA_MODEL', 'llama3.2'))
        self.timeout = int(getattr(settings, 'OLLAMA_TIMEOUT', os.getenv('OLLAMA_TIMEOUT', '300')))

    def _make_request(self, endpoint: str, data: Dict) -> Optional[Dict]:
        try:
            base_url = self.base_url.rstrip('/')
            endpoint = endpoint if endpoint.startswith('/') else f'/{endpoint}'
            url = f"{base_url}{endpoint}"
            
            logger.info(f"Making Ollama request to: {url}")
            logger.info(f"Using model: {data.get('model', 'unknown')}")
            logger.debug(f"Request data: {data}")
            
            response = requests.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"Ollama API HTTP error: {str(e)}"
            if hasattr(e.response, 'status_code'):
                error_msg += f" (Status: {e.response.status_code})"
            if hasattr(e.response, 'url'):
                error_msg += f" | URL: {e.response.url}"
            if hasattr(e.response, 'text'):
                error_msg += f" | Response: {e.response.text}"
            logger.error(error_msg)
            
            if hasattr(e.response, 'status_code') and e.response.status_code == 404:
                model_name = data.get('model', 'unknown')
                logger.error(f"Model '{model_name}' may not exist. Please verify the model is available with: ollama list")
            
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {str(e)}")
            return None

    def generate_question(
        self,
        category_name: str,
        topic_name: str,
        subtopic_name: Optional[str],
        difficulty: str,
        context: Optional[str] = None
    ) -> Optional[Dict]:
        context_str = f"Category: {category_name}\nTopic: {topic_name}"
        if subtopic_name:
            context_str += f"\nSubtopic: {subtopic_name}"
        if context:
            context_str += f"\nAdditional Context: {context}"
        
        difficulty_instructions = {
            'easy': """EASY difficulty questions should be:
            - Simple, straightforward questions that test basic knowledge
            - Examples: "What is Python?", "What is a variable?", "Explain what is a function?"
            - Should be answerable in 30-60 seconds
            - Focus on fundamental concepts and definitions
            - Avoid complex design or architecture questions
            - Questions should be clear and direct, suitable for voice-based interviews""",
            'medium': """MEDIUM difficulty questions should be:
            - Somewhat challenging conceptual questions
            - Can include explanatory questions that require understanding
            - Can include design questions that test practical application
            - Examples: "How does Python handle memory management?", "Design a simple REST API"
            - Should be answerable in 60-120 seconds
            - Test both knowledge and ability to explain concepts""",
            'hard': """HARD difficulty questions should be:
            - Tricky questions that test deep domain knowledge
            - Complex conceptual questions requiring advanced understanding
            - Questions that test problem-solving and critical thinking
            - Examples: "Explain the trade-offs between different database indexing strategies"
            - Should be answerable in 120-180 seconds
            - Focus on advanced concepts, edge cases, and deep technical knowledge"""
        }
        
        difficulty_guide = difficulty_instructions.get(difficulty.lower(), difficulty_instructions['medium'])
        
        prompt = f"""You are an expert interview question generator for technical assessments.
            Context:
            {context_str}
            Difficulty Level: {difficulty.upper()}
            
            {difficulty_guide}
            
            Generate a comprehensive interview question with the following structure:
            1. A clear, well-formulated question that tests knowledge and understanding
            2. An expected answer that covers key points
            3. Important keywords that should appear in a good answer
            4. An estimated time (in seconds) a candidate should take to answer
            5. Red flags that indicate poor answers
            6. An ideal answer summary
            Return your response as a JSON object with the following structure:
            {{
                "question": "The interview question text",
                "expected_answer": "A comprehensive expected answer covering all important aspects",
                "keywords": ["keyword1", "keyword2", "keyword3", ...],
                "time_in_seconds": 120,
                "red_flags": ["red flag 1", "red flag 2", ...],
                "ideal_answer_summary": "A concise summary of what an ideal answer should contain"
            }}
            The question should be specific to {topic_name}{' and ' + subtopic_name if subtopic_name else ''}.
            IMPORTANT: For EASY questions, generate simple, direct questions like "What is X?" or "Explain Y in simple terms".
        """

        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        response = self._make_request("/api/generate", data)
        
        if response and 'response' in response:
            try:
                response_text = response['response']
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0].strip()
                question_data = json.loads(response_text)
                required_fields = ['question', 'expected_answer', 'keywords', 'time_in_seconds']
                if all(field in question_data for field in required_fields):
                    question_data.setdefault('red_flags', [])
                    question_data.setdefault('ideal_answer_summary', '')
                    return question_data
                else:
                    logger.warning(f"Generated question missing required fields: {question_data}")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from Ollama: {str(e)}")
                logger.error(f"Response text: {response.get('response', '')}")
                return None
        
        return None

    def generate_subtopic_name(
        self,
        category_name: str,
        topic_name: str,
        topic_description: Optional[str] = None
    ) -> Optional[str]:
        description_context = ""
        if topic_description:
            description_context = f"\nTopic Description: {topic_description}"
        
        prompt = f"""You are an expert at categorizing technical knowledge domains.

            Category: {category_name}
            Topic: {topic_name}{description_context}
            Generate a specific, relevant subtopic name that would be appropriate for this topic.
            The subtopic should be:
            1. Specific and focused (not too broad)
            2. Relevant to the topic and category
            3. A single, concise name (2-5 words maximum)
            4. Professional and appropriate for interview questions
            Return ONLY the subtopic name as a plain text string, nothing else.
            Do not include any explanations, prefixes, or additional text.
            Just the subtopic name.

            Example: If Category is "Software Engineering" and Topic is "Full Stack Developer", 
            a good subtopic might be "Django Framework" or "React Components" or "Database Design".
            Subtopic name:
        """

        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        response = self._make_request("/api/generate", data)
        
        if response and 'response' in response:
            try:
                subtopic_name = response['response'].strip()
                subtopic_name = subtopic_name.replace('"', '').replace("'", '').strip()
                subtopic_name = subtopic_name.replace('Subtopic name:', '').replace('Subtopic:', '').strip()
                subtopic_name = subtopic_name.split('\n')[0].strip()
                
                if subtopic_name and len(subtopic_name) > 0:
                    return subtopic_name
                else:
                    logger.warning("Generated subtopic name is empty")
                    return None
            except Exception as e:
                logger.error(f"Failed to parse subtopic name from Ollama: {str(e)}")
                return None
        
        return None

    def generate_questions_batch(
        self,
        category_name: str,
        topic_name: str,
        subtopic_name: Optional[str],
        difficulty: str,
        count: int,
        context: Optional[str] = None
    ) -> List[Dict]:
        questions = []
        for i in range(count):
            question = self.generate_question(
                category_name=category_name,
                topic_name=topic_name,
                subtopic_name=subtopic_name,
                difficulty=difficulty,
                context=context
            )
            if question:
                questions.append(question)
            else:
                logger.warning(f"Failed to generate question {i+1}/{count}")
        return questions

