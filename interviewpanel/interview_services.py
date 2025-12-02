"""
Refactored interview services with separated concerns.
- Prompt engineering separated into PromptBuilder
- Score calculation separated into ScoreCalculator
- Input sanitization separated into PromptSanitizer
- JSON parsing separated into JSONParser
- Proper error handling with custom exceptions
"""
import logging
from typing import Dict, Optional, List
from django.utils import timezone
from questionbank.ollama_service import OllamaService
from .models import InterviewSession, InterviewAnswer, InterviewPanelQuestion, InterviewPanel
from questionbank.models import Question
from utils.exceptions import (
    LLMServiceError,
    PromptInjectionError,
    JSONParseError,
    ScoreCalculationError,
    InvalidAnalysisError,
    QuestionSelectionError
)
from utils.prompt_builder import PromptBuilder
from utils.prompt_sanitizer import PromptSanitizer
from utils.json_parser import JSONParser
from .score_calculator import ScoreCalculator

logger = logging.getLogger(__name__)


class InterviewGreetingService:
    
    def __init__(self):
        self.ollama_service = OllamaService()
    
    def generate_greeting(self, interview_panel: InterviewPanel, candidate_name: str) -> str:
        candidate_name = candidate_name.strip().title()
        simple_greeting = f"Welcome {candidate_name}! I am Vecna, the interviewer for the {interview_panel.name}. Thank you for joining us for the interview. This is a voice-based interview, so please speak naturally and clearly. Let's begin!"
        return simple_greeting


class AnswerAnalysisService:
    """Service for analyzing candidate answers - separated concerns"""
    
    def __init__(self):
        self.ollama_service = OllamaService()
    
    def analyze_answer(
        self,
        answer: InterviewAnswer,
        question: Question,  # Changed from InterviewPanelQuestion to Question
        session: InterviewSession
    ) -> Dict:
        # Get transcription
        transcription = answer.full_transcription or answer.transcription or ""

        if not transcription:
            logger.warning(f"No transcription for answer {answer.uuid}")
            return {
                'score': 0,
                'next_action': 'keep_level_same',
                'analysis_summary': 'No transcription available',
                'score_technical': 0,
                'score_domain_knowledge': 0,
                'score_communication': 0,
                'score_problem_solving': 0,
                'score_creativity': 0,
                'score_attention_to_detail': 0,
                'score_time_management': 0,
                'score_stress_management': 0,
                'score_adaptability': 0,
                'score_confidence': 0,
                'keywords_matched': [],
                'keywords_coverage': 0.0,
                'red_flags_detected': []
            }

        try:
            # Sanitize transcription (raises PromptInjectionError if injection detected)
            sanitized_transcription = PromptSanitizer.sanitize_transcription(transcription)

            # Get question details
            # Note: question is already the Question model instance (from answer.question.question)
            # where answer.question is InterviewPanelQuestion and .question is the Question FK
            expected_answer = question.expected_answer or ""
            expected_keywords = question.expected_keywords or []
            difficulty_level = question.difficulty_level
            red_flags = question.red_flags or []

            # Build prompt using PromptBuilder
            prompt = PromptBuilder.build_analysis_prompt(
                question_text=question.question,  # question.question is the text field
                expected_answer=expected_answer,
                expected_keywords=expected_keywords,
                difficulty_level=difficulty_level,
                red_flags=red_flags,
                transcription=sanitized_transcription,
                questions_asked=session.questions_asked_count,
                total_questions=session.total_questions_available
            )

            # Make LLM request
            data = {
                "model": self.ollama_service.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }

            response = self.ollama_service._make_request("/api/generate", data)
            if not response or 'response' not in response:
                raise LLMServiceError("No response from LLM service")

            # Parse JSON response (raises JSONParseError if parsing fails)
            required_fields = [
                'score_technical', 'score_domain_knowledge', 'score_communication',
                'score_problem_solving', 'score_creativity', 'score_attention_to_detail',
                'score_time_management', 'score_stress_management', 'score_adaptability',
                'score_confidence', 'analysis_summary', 'next_action'
            ]

            analysis = JSONParser.parse_llm_response(
                response['response'],
                required_fields=required_fields
            )

            # Validate next_action
            valid_actions = ['drill_up', 'drill_down', 'keep_level_same', 'end_of_interview']
            next_action = analysis.get('next_action', 'keep_level_same')
            if next_action not in valid_actions:
                logger.warning(f"Invalid next_action: {next_action}, using keep_level_same")
                next_action = 'keep_level_same'

            # Validate end_of_interview condition
            questions_percentage = (
                (session.questions_asked_count / session.total_questions_available * 100)
                if session.total_questions_available > 0 else 0
            )
            if next_action == 'end_of_interview' and questions_percentage < 50:
                logger.info(f"Cannot end interview yet ({questions_percentage:.1f}% asked)")
                next_action = 'keep_level_same'
                analysis['analysis_summary'] += (
                    " (Interview cannot end yet - less than 50% questions asked)"
                )

            # Extract and validate scores
            scores = ScoreCalculator.validate_analysis_scores(analysis)

            # Get weights from question
            # Note: question is the Question model instance
            weights = {
                'technical': question.score_weight_technical or 0.5,
                'domain_knowledge': question.score_weight_domain_knowledge or 0.3,
                'communication': question.score_weight_communication or 0.1,
                'problem_solving': question.score_weight_problem_solving or 0.05,
                'creativity': question.score_weight_creativity or 0.05,
                'attention_to_detail': question.score_weight_attention_to_detail or 0.05,
                'time_management': question.score_weight_time_management or 0.05,
                'stress_management': question.score_weight_stress_management or 0.05,
                'adaptability': question.score_weight_adaptability or 0.05,
                'confidence': question.score_weight_confidence or 0.05,
            }

            # Calculate weighted total score (normalizes weights automatically)
            total_score = ScoreCalculator.calculate_weighted_score(
                scores=scores,
                weights=weights,
                normalize=True  # Ensure weights sum to 1.0
            )

            # Build result dictionary
            result = {
                'score': int(total_score),
                'score_technical': scores.get('technical', 0),
                'score_domain_knowledge': scores.get('domain_knowledge', 0),
                'score_communication': scores.get('communication', 0),
                'score_problem_solving': scores.get('problem_solving', 0),
                'score_creativity': scores.get('creativity', 0),
                'score_attention_to_detail': scores.get('attention_to_detail', 0),
                'score_time_management': scores.get('time_management', 0),
                'score_stress_management': scores.get('stress_management', 0),
                'score_adaptability': scores.get('adaptability', 0),
                'score_confidence': scores.get('confidence', 0),
                'keywords_matched': analysis.get('keywords_matched', []),
                'keywords_coverage': float(analysis.get('keywords_coverage', 0.0)),
                'red_flags_detected': analysis.get('red_flags_detected', []),
                'analysis_summary': analysis.get('analysis_summary', ''),
                'next_action': next_action
            }

            return result

        except (PromptInjectionError, LLMServiceError, JSONParseError, ScoreCalculationError):
            # Re-raise expected exceptions
            raise
        except Exception as e:
            # Log and re-raise as InvalidAnalysisError
            logger.error(f"Unexpected error analyzing answer: {str(e)}", exc_info=True)
            raise InvalidAnalysisError(f"Failed to analyze answer: {str(e)}") from e


class AdaptiveQuestionSelector:
    """Service for selecting next question - improved logic with loop protection"""
    
    # Maximum attempts to find a question before giving up
    MAX_SELECTION_ATTEMPTS = 3
    
    def get_next_question(
        self,
        session: InterviewSession,
        next_action: str,
        current_difficulty: str
    ) -> Optional[InterviewPanelQuestion]:
        """
        Get next question based on adaptive strategy with improved logic.
        
        Args:
            session: Interview session
            next_action: Next action (drill_up, drill_down, keep_level_same)
            current_difficulty: Current difficulty level
            
        Returns:
            Selected question or None if no questions available
            
        Raises:
            QuestionSelectionError: If selection fails critically
        """
        try:
            if not session.interview_panel_candidate:
                raise QuestionSelectionError("No interview_panel_candidate in session")
            
            panel = session.interview_panel_candidate.interview_panel
            
            # Get all available questions for the panel
            all_questions = InterviewPanelQuestion.objects.filter(
                interview_panel=panel,
                is_deleted=False,
                is_active=True
            ).select_related('question')
            
            if not all_questions.exists():
                logger.warning(f"No questions available for panel {panel.uuid}")
                return None
            
            # Get already asked questions (exclude greeting answers which have question=None)
            all_answers = InterviewAnswer.objects.filter(
                interview_session=session,
                is_deleted=False
            )
            logger.info(f"Total answers for session: {all_answers.count()} (including greeting)")
            
            # Filter out greeting answers (round 0) which have question=None
            answered_questions = all_answers.filter(
                question__isnull=False  # Exclude greeting answers (round 0) which have no question
            ).values_list('question_id', flat=True)
            
            answered_question_ids = list(answered_questions)
            logger.info(f"Already answered question IDs (excluding greeting): {answered_question_ids}")
            logger.info(f"Count: {len(answered_question_ids)}")
            
            # Filter out already asked questions
            available_questions = all_questions.exclude(id__in=answered_question_ids)
            logger.info(f"Available questions after filtering: {available_questions.count()}")
            
            if not available_questions.exists():
                logger.info("All questions have been asked - interview should end")
                return None
            
            # Determine target difficulty with improved logic
            target_difficulty = self._determine_target_difficulty(
                next_action=next_action,
                current_difficulty=current_difficulty,
                available_questions=available_questions
            )
            
            # Try to get question at target difficulty
            difficulty_questions = available_questions.filter(
                question__difficulty_level=target_difficulty
            )
            
            if difficulty_questions.exists():
                selected = difficulty_questions.first()
                logger.info(f"Selected {target_difficulty} question: {selected.question.name}")
                return selected
            
            # Fallback: try other difficulties in order of preference
            fallback_difficulties = self._get_fallback_difficulties(target_difficulty)
            
            for fallback_diff in fallback_difficulties:
                fallback_questions = available_questions.filter(
                    question__difficulty_level=fallback_diff
                )
                if fallback_questions.exists():
                    selected = fallback_questions.first()
                    logger.info(f"Selected {fallback_diff} question (fallback): {selected.question.name}")
                    return selected
            
            # Last resort: return any available question
            logger.warning("No questions at preferred difficulty, returning any available question")
            return available_questions.first()
            
        except QuestionSelectionError:
            # Re-raise expected exceptions
            raise
        except Exception as e:
            logger.error(f"Error selecting next question: {str(e)}", exc_info=True)
            raise QuestionSelectionError(f"Failed to select question: {str(e)}") from e
    
    def _determine_target_difficulty(
        self,
        next_action: str,
        current_difficulty: str,
        available_questions: 'QuerySet'
    ) -> str:
        """
        Determine target difficulty with improved logic.
        
        Args:
            next_action: Next action
            current_difficulty: Current difficulty
            available_questions: Available questions queryset
            
        Returns:
            Target difficulty level
        """
        if next_action == 'drill_up':
            difficulty_map = {'easy': 'medium', 'medium': 'hard', 'hard': 'hard'}
            target = difficulty_map.get(current_difficulty, 'medium')
        elif next_action == 'drill_down':
            difficulty_map = {'easy': 'easy', 'medium': 'easy', 'hard': 'medium'}
            target = difficulty_map.get(current_difficulty, 'medium')
        else:  # keep_level_same
            target = current_difficulty
        
        # Verify target difficulty has available questions
        if available_questions.filter(question__difficulty_level=target).exists():
            return target
        
        # If target difficulty has no questions, use current difficulty
        if available_questions.filter(question__difficulty_level=current_difficulty).exists():
            logger.info(f"Target difficulty {target} has no questions, using current {current_difficulty}")
            return current_difficulty
        
        # Last resort: return target anyway (fallback logic will handle it)
        return target
    
    def _get_fallback_difficulties(self, target_difficulty: str) -> List[str]:
        """
        Get fallback difficulties in order of preference.
        
        Args:
            target_difficulty: Target difficulty
            
        Returns:
            List of fallback difficulties
        """
        if target_difficulty == 'hard':
            return ['medium', 'easy']
        elif target_difficulty == 'medium':
            return ['easy', 'hard']
        else:  # easy
            return ['medium', 'hard']
