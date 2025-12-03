import re
import logging
from .exceptions import PromptInjectionError

logger = logging.getLogger(__name__)


class PromptSanitizer:
    """Sanitizes user input to prevent prompt injection attacks"""
    
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|all)\s+instructions?',
        r'forget\s+(previous|all)\s+instructions?',
        r'disregard\s+(previous|all)\s+instructions?',
        r'you\s+are\s+now',
        r'act\s+as\s+if',
        r'pretend\s+to\s+be',
        r'next_action\s*=\s*end_of_interview',
        r'return\s+next_action',
        r'system\s*:',
        r'user\s*:',
        r'<\|.*?\|>',
        r'\[INST\]',
        r'\[/INST\]',
    ]
    
    MAX_TRANSCRIPTION_LENGTH = 10000
    
    DANGEROUS_CHARS = ['<', '>', '{', '}', '[', ']', '|']
    
    @classmethod
    def sanitize_transcription(cls, transcription: str) -> str:
        if not transcription:
            return ""
        
        if len(transcription) > cls.MAX_TRANSCRIPTION_LENGTH:
            logger.warning(f"Transcription too long ({len(transcription)} chars), truncating")
            transcription = transcription[:cls.MAX_TRANSCRIPTION_LENGTH]
        
        transcription_lower = transcription.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, transcription_lower, re.IGNORECASE):
                logger.error(f"Potential prompt injection detected: {pattern}")
                raise PromptInjectionError(
                    f"Invalid input detected. Please provide a valid answer to the question."
                )
        
        sanitized = transcription
        for char in cls.DANGEROUS_CHARS:
            sanitized = sanitized.replace(char, '')
        
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    @classmethod
    def sanitize_string(cls, text: str, max_length: int = 1000) -> str:
        if not text:
            return ""
        
        if len(text) > max_length:
            text = text[:max_length]
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

