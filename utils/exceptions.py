"""
Custom exceptions for interview panel services.
Provides structured error handling instead of silent failures.
"""


class InterviewServiceError(Exception):
    """Base exception for interview service errors"""
    pass


class LLMServiceError(InterviewServiceError):
    """Error communicating with LLM service"""
    pass


class PromptInjectionError(InterviewServiceError):
    """Detected potential prompt injection attempt"""
    pass


class JSONParseError(InterviewServiceError):
    """Failed to parse JSON response from LLM"""
    pass


class ScoreCalculationError(InterviewServiceError):
    """Error calculating scores"""
    pass


class QuestionSelectionError(InterviewServiceError):
    """Error selecting next question"""
    pass


class InvalidAnalysisError(InterviewServiceError):
    """Invalid analysis result from LLM"""
    pass

