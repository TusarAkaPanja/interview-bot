import base64
import json
import logging
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Avg
from django.conf import settings
from .models import InterviewAnswer, InterviewSession, InterviewPanelQuestion, InterviewPanelCandidate, InterviewReportAnswerwiseFeedback
from .interview_services import InterviewGreetingService, AnswerAnalysisService, AdaptiveQuestionSelector
from .session_manager import SessionManager
from utils.exceptions import (
    LLMServiceError,
    PromptInjectionError,
    JSONParseError,
    ScoreCalculationError,
    InvalidAnalysisError,
    QuestionSelectionError
)
from utils.prompt_sanitizer import PromptSanitizer
from questionbank.ollama_service import OllamaService
from datetime import datetime
import os
import html as html_escape
from pathlib import Path

logger = logging.getLogger(__name__)

def update_session_cumulative_score(session):
    """
    Calculate and update cumulative_score for a session.
    
    Formula for each answer:
    1. Technical score = (score_technical + score_domain_knowledge + score_problem_solving) / 3 * 3
       (3 components, each 0-1, normalized and weighted by 3)
    2. Behavioral score = (score_communication + score_creativity + score_attention_to_detail + 
                          score_time_management + score_stress_management + score_adaptability + 
                          score_confidence) / 7 * 3
       (7 components, each 0-1, normalized and weighted by 3)
    3. Psychological score = (score_confidence + score_stress_management) / 2 * 2
       (2 components, each 0-1, normalized and weighted by 2)
    
    4. Answer score = (Technical + Behavioral + Psychological) / (3 + 3 + 2) = / 8
    5. Cumulative score = Average of all answer scores * 100
    """
    try:
        # Get all answered questions (exclude greeting round)
        answers = InterviewAnswer.objects.filter(
            interview_session=session,
            question__isnull=False,
            is_deleted=False
        )
        
        if not answers.exists():
            session.cumulative_score = 0.0
            session.save(update_fields=['cumulative_score'])
            logger.info(f"No answers found for session {session.uuid}, setting cumulative_score to 0")
            return 0.0
        
        answer_scores = []
        for answer in answers:
            # Technical: 3 components, each 0-1
            technical_sum = (
                (answer.score_technical or 0.0) + 
                (answer.score_domain_knowledge or 0.0) + 
                (answer.score_problem_solving or 0.0)
            )
            technical_normalized = technical_sum / 3.0  # Normalize to 0-1
            technical_weighted = technical_normalized * 3  # Weight by 3
            
            # Behavioral: 7 components, each 0-1
            behavioral_sum = (
                (answer.score_communication or 0.0) + 
                (answer.score_creativity or 0.0) + 
                (answer.score_attention_to_detail or 0.0) + 
                (answer.score_time_management or 0.0) + 
                (answer.score_stress_management or 0.0) + 
                (answer.score_adaptability or 0.0) + 
                (answer.score_confidence or 0.0)
            )
            behavioral_normalized = behavioral_sum / 7.0  # Normalize to 0-1
            behavioral_weighted = behavioral_normalized * 3  # Weight by 3
            
            # Psychological: 2 components, each 0-1
            psychological_sum = (
                (answer.score_confidence or 0.0) + 
                (answer.score_stress_management or 0.0)
            )
            psychological_normalized = psychological_sum / 2.0  # Normalize to 0-1
            psychological_weighted = psychological_normalized * 2  # Weight by 2
            
            # Answer score = (Technical + Behavioral + Psychological) / 8
            answer_score = (technical_weighted + behavioral_weighted + psychological_weighted) / 8.0
            answer_scores.append(answer_score)
        
        if answer_scores:
            # Calculate average of all answer scores
            avg_answer_score = sum(answer_scores) / len(answer_scores)
            # Convert to percentage (0-100)
            cumulative_score = avg_answer_score * 100
            cumulative_score = round(cumulative_score, 2)
        else:
            cumulative_score = 0.0
        
        session.cumulative_score = cumulative_score
        session.save(update_fields=['cumulative_score'])
        logger.info(f"Updated cumulative_score for session {session.uuid}: {cumulative_score}/100 from {len(answer_scores)} answers")
        return cumulative_score
    except Exception as e:
        logger.error(f"Error updating cumulative_score for session {session.uuid}: {str(e)}", exc_info=True)
        return None

# Set library path for WeasyPrint on macOS (must be before WeasyPrint import)
if os.name == 'posix' and '/opt/homebrew/lib' not in os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', ''):
    current_path = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
    os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f'/opt/homebrew/lib:{current_path}' if current_path else '/opt/homebrew/lib'

try:
    from weasyprint import HTML, CSS
except OSError as e:
    logger.error(f"Failed to import WeasyPrint. Please ensure system dependencies are installed: {str(e)}")
    logger.error("On macOS, run: brew install cairo pango gdk-pixbuf libffi")
    logger.error("And set: export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib")
    raise

channel_layer = get_channel_layer()
greeting_service = InterviewGreetingService()
analysis_service = AnswerAnalysisService()
question_selector = AdaptiveQuestionSelector()

# Lazy initialization of ASR service to avoid import-time errors
_asr_service = None
_asr_service_initialized = False

def get_asr_service():
    """Lazy initialization of ASR service - only loads when first needed"""
    global _asr_service, _asr_service_initialized
    
    if _asr_service_initialized:
        return _asr_service
    
    _asr_service_initialized = True
    
    try:
        from .asr_service import WhisperASRService
        _asr_service = WhisperASRService(model_size=os.getenv('WHISPER_MODEL_SIZE', 'small'))
        if _asr_service.whisper_available:
            logger.info("ASR service initialized: faster-whisper (small model)")
            return _asr_service
        else:
            logger.warning("faster-whisper not available, trying Ollama ASR")
    except ImportError as e:
        logger.warning(f"faster-whisper not installed: {str(e)}")
    except Exception as e:
        logger.warning(f"Failed to initialize faster-whisper: {str(e)}")
    
    try:
        from .asr_service import ASRService
        _asr_service = ASRService()
        logger.info("ASR service initialized: Ollama ASR (fallback)")
        return _asr_service
    except Exception as e:
        logger.error(f"Failed to initialize any ASR service: {str(e)}")
        _asr_service = None
        return None


@shared_task
def process_buffered_audio(answer_uuid, audio_chunks, session_uuid):
    try:
        if not SessionManager.is_session_active(session_uuid):
            logger.warning(f"Session {session_uuid} is inactive, skipping audio processing")
            return {'status': 'skipped', 'message': 'Session inactive'}
        
        answer = InterviewAnswer.objects.get(uuid=answer_uuid)
        
        # Get ASR service (lazy initialization)
        asr_service = get_asr_service()
        if not asr_service:
            logger.error("ASR service not available")
            return {'status': 'error', 'message': 'ASR service not initialized'}
        
        # Combine and decode all audio chunks
        combined_audio_data = b''
        for chunk_base64 in audio_chunks:
            combined_audio_data += base64.b64decode(chunk_base64)
        
        # Transcribe combined audio
        sample_rate = 16000  # Standard sample rate for audio processing
        transcription = asr_service.transcribe_audio(combined_audio_data, sample_rate=sample_rate)
        
        # Calculate audio duration for logging (after transcription attempt)
        audio_duration_seconds = len(combined_audio_data) / (sample_rate * 2)  # 16-bit = 2 bytes per sample
        logger.info(f"Processing audio with duration {audio_duration_seconds:.3f}s for answer {answer_uuid}")
        
        # Track skip count for auto-finalization
        from .audio_buffer import audio_buffer
        if not transcription or transcription.strip() == "":
            # Increment skip count
            current_skip_count = audio_buffer.get_skip_count(answer_uuid)
            skip_count = current_skip_count + 1
            audio_buffer.skip_counts[answer_uuid] = skip_count
            
            logger.warning(f"No speech detected in audio (duration: {audio_duration_seconds:.3f}s). "
                          f"Skip count for answer {answer_uuid}: {skip_count}")
            
            # If threshold+ consecutive skips, trigger finalization to prevent deadlock
            skip_threshold = int(os.getenv('CONSECUTIVE_SKIPS_THRESHOLD', '1'))
            if skip_count >= skip_threshold:
                logger.warning(f"{skip_threshold}+ consecutive skips detected for answer {answer_uuid}. "
                              f"Triggering finalization to prevent deadlock.")
                # Check if we have any previous transcription
                answer.refresh_from_db()
                if answer.full_transcription or answer.transcription:
                    # We have transcription, finalize with what we have
                    logger.info(f"Finalizing answer {answer_uuid} with existing transcription after {skip_count} skips")
                    from .tasks import finalize_answer
                    finalize_answer.delay(answer_uuid, session_uuid)
                else:
                    # No transcription at all - mark as timeout
                    logger.warning(f"No transcription found after {skip_count} skips. Marking as timeout.")
                    answer.status = 'timeout'
                    answer.answered_at = timezone.now()
                    answer.analysis_summary = "No speech detected after multiple attempts."
                    answer.save()
                    # Still trigger finalization to proceed
                    from .tasks import finalize_answer
                    finalize_answer.delay(answer_uuid, session_uuid)
            
            return {'status': 'skipped', 'message': 'No speech detected', 'skip_count': skip_count}
        
        # Reset skip count on successful transcription
        if answer_uuid in audio_buffer.skip_counts:
            audio_buffer.skip_counts[answer_uuid] = 0
        
        transcription = transcription.strip()
        
        # Update answer with transcription (append to full transcription)
        if not answer.full_transcription:
            answer.full_transcription = transcription
        else:
            answer.full_transcription += " " + transcription
        
        # Also update transcription field for real-time display
        if not answer.transcription:
            answer.transcription = transcription
        else:
            answer.transcription += " " + transcription
        
        answer.save()
        
        # Save transcription to TurnDetector state (persists until turn out)
        from .turn_detection import turn_detector
        turn_detector.add_transcription(session_uuid, transcription)
        
        # Broadcast transcription update via WebSocket for real-time display only
        # Analysis will only happen after round ends (not per chunk)
        if SessionManager.is_session_active(session_uuid):
            room_group_name = f'interview_{session_uuid}'
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'transcription_update',
                    'character': 'candidate',
                    'message': answer.transcription or transcription,  # Show cumulative transcription
                    'answer_uuid': answer_uuid,
                    'is_partial': True  # Indicate this is partial, not final
                }
            )
        
        # Update turn detector - transcription means speech detected
        # But don't trigger analysis yet - only after round ends
        # Note: We update turn detector but don't auto-end here
        # The periodic check or manual end_round will handle that
        
        return {'status': 'success', 'transcription': transcription, 'chunks_processed': len(audio_chunks)}
    except InterviewAnswer.DoesNotExist:
        logger.warning(f"Answer {answer_uuid} not found")
        return {'status': 'error', 'message': 'Answer not found'}
    except Exception as e:
        logger.error(f"Error processing buffered audio: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def analyze_and_score_answer(answer_uuid, session_uuid):
    try:
        answer = InterviewAnswer.objects.get(uuid=answer_uuid)
        session = answer.interview_session
        
        answer.refresh_from_db()
        
        logger.info(f"Analyzing answer {answer_uuid}, round {answer.round_number}, "
                   f"has transcription: {bool(answer.full_transcription or answer.transcription)}, "
                   f"transcription length: {len(answer.full_transcription or answer.transcription or '')}")
        
        if not answer.full_transcription and not answer.transcription:
            logger.warning(f"No transcription for answer {answer_uuid} (round {answer.round_number}) - "
                          f"full_transcription: '{answer.full_transcription}', "
                          f"transcription: '{answer.transcription}'. "
                          f"This might indicate turn ended too early or transcription not saved yet.")
            with transaction.atomic():
                answer.refresh_from_db()
                answer.status = 'answered'
                answer.answered_at = timezone.now()
                answer.analyzed_at = timezone.now()
                answer.score = 0
                answer.analysis_summary = "No response provided (timeout)."
                answer.next_action = 'keep_level_same'  # Default action for empty answers
                answer.save()
                
                # Update session
                session.refresh_from_db()
                session.questions_asked_count = F('questions_asked_count') + 1
                session.current_round = F('current_round') + 1
                session.save()
                session.refresh_from_db()
            
            # Broadcast scoring update (even for empty answer)
            if SessionManager.is_session_active(session_uuid):
                room_group_name = f'interview_{session_uuid}'
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'scoring_update',
                        'character': 'ai',
                        'score': 0,
                        'answer_uuid': str(answer.uuid),
                        'summary': 'No response provided (timeout).',
                        'next_action': 'keep_level_same'
                    }
                )
            
            # Proceed to next question
            select_and_send_next_question.delay(session_uuid, 'keep_level_same')
            return {'status': 'success', 'message': 'Empty answer processed (timeout), proceeding to next question'}
        
        # Get question for regular rounds
        if not answer.question:
            return {'status': 'error', 'message': 'No question associated with answer'}
        
        # Refresh answer from DB to ensure we have latest transcription
        answer.refresh_from_db()
        
        question = answer.question.question
        
        # Analyze answer with proper error handling
        try:
            analysis = analysis_service.analyze_answer(answer, question, session)
        except PromptInjectionError as e:
            logger.error(f"Prompt injection detected for answer {answer_uuid}: {str(e)}")
            # Handle injection attempt - mark answer but don't proceed
            with transaction.atomic():
                answer.refresh_from_db()
                answer.status = 'answered'
                answer.answered_at = timezone.now()
                answer.analyzed_at = timezone.now()
                answer.score = 0
                answer.analysis_summary = "Invalid input detected. Please provide a valid answer."
                answer.next_action = 'keep_level_same'
                answer.save()
            
            # Don't proceed to next question - end interview or notify
            if SessionManager.is_session_active(session_uuid):
                room_group_name = f'interview_{session_uuid}'
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'scoring_update',
                        'character': 'ai',
                        'score': 0,
                        'answer_uuid': str(answer.uuid),
                        'summary': 'Invalid input detected. Please provide a valid answer.',
                        'next_action': 'keep_level_same'
                    }
                )
            return {'status': 'error', 'message': 'Prompt injection detected'}
        except (LLMServiceError, JSONParseError, ScoreCalculationError, InvalidAnalysisError) as e:
            logger.error(f"Analysis failed for answer {answer_uuid}: {str(e)}", exc_info=True)
            # Use fallback analysis
            analysis = {
                'score': 50,
                'next_action': 'keep_level_same',
                'analysis_summary': f'Analysis unavailable: {str(e)}',
                'score_technical': 50,
                'score_domain_knowledge': 50,
                'score_communication': 50,
                'score_problem_solving': 50,
                'score_creativity': 50,
                'score_attention_to_detail': 50,
                'score_time_management': 50,
                'score_stress_management': 50,
                'score_adaptability': 50,
                'score_confidence': 50,
                'keywords_matched': [],
                'keywords_coverage': 0.0,
                'red_flags_detected': []
            }
        
        # Update answer with analysis results
        answer.score = analysis['score']
        answer.score_technical = analysis.get('score_technical', 0)
        answer.score_domain_knowledge = analysis.get('score_domain_knowledge', 0)
        answer.score_communication = analysis.get('score_communication', 0)
        answer.score_problem_solving = analysis.get('score_problem_solving', 0)
        answer.score_creativity = analysis.get('score_creativity', 0)
        answer.score_attention_to_detail = analysis.get('score_attention_to_detail', 0)
        answer.score_time_management = analysis.get('score_time_management', 0)
        answer.score_stress_management = analysis.get('score_stress_management', 0)
        answer.score_adaptability = analysis.get('score_adaptability', 0)
        answer.score_confidence = analysis.get('score_confidence', 0)
        answer.keywords_matched = analysis.get('keywords_matched', [])
        answer.keywords_coverage = analysis.get('keywords_coverage', 0.0)
        answer.red_flags_detected = analysis.get('red_flags_detected', [])
        answer.analysis_summary = analysis.get('analysis_summary', '')
        answer.next_action = analysis.get('next_action', 'keep_level_same')
        answer.status = 'answered'
        answer.answered_at = timezone.now()
        answer.analyzed_at = timezone.now()
        answer.save()
        
        # Update session
        session.questions_asked_count += 1
        session.current_round += 1
        
        # Update difficulty based on next action
        next_action = analysis.get('next_action', 'keep_level_same')
        if next_action == 'drill_up':
            if session.current_difficulty == 'easy':
                session.current_difficulty = 'medium'
            elif session.current_difficulty == 'medium':
                session.current_difficulty = 'hard'
        elif next_action == 'drill_down':
            if session.current_difficulty == 'hard':
                session.current_difficulty = 'medium'
            elif session.current_difficulty == 'medium':
                session.current_difficulty = 'easy'
        
        session.save()
        
        # Update cumulative score after each answer
        update_session_cumulative_score(session)
        
        # Update candidate statistics
        if session.interview_panel_candidate:
            session.interview_panel_candidate.number_of_questions_answered += 1
            session.interview_panel_candidate.score += analysis['score']
            session.interview_panel_candidate.save()
        
        # Broadcast scoring update via WebSocket
        room_group_name = f'interview_{session_uuid}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'scoring_update',
                'character': 'ai',
                'score': analysis['score'],
                'answer_uuid': answer_uuid,
                'summary': analysis.get('analysis_summary', ''),
                'next_action': next_action
            }
        )
        
        # Select and send next question if not ending interview
        # Check if session is still active before proceeding
        if not SessionManager.is_session_active(session_uuid):
            logger.warning(f"Session {session_uuid} is inactive, skipping next question")
            return {'status': 'skipped', 'message': 'Session inactive'}
        
        # Check if this was greeting round - already handled above
        # For regular rounds, proceed with next question
        if next_action != 'end_of_interview':
            select_and_send_next_question.delay(session_uuid, next_action)
        else:
            # End interview (only if session still active)
            if SessionManager.is_session_active(session_uuid):
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'interview_completed',
                        'character': 'ai',
                        'message': 'Interview completed successfully'
                    }
                )
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            # Update cumulative score when session is completed
            update_session_cumulative_score(session)
            
            # Generate interview report
            logger.info(f"Triggering report generation for completed session {session_uuid}")
            generate_interview_report.delay(session_uuid)
        
        return {'status': 'success', 'analysis': analysis}
    except Exception as e:
        logger.error(f"Unexpected error in analyze_and_score_answer: {str(e)}", exc_info=True)
        return {'status': 'error', 'message': str(e)}


@shared_task
def select_and_send_next_question(session_uuid, next_action, attempt_count=0):
    """
    Select next question adaptively and send via WebSocket.
    Includes infinite loop protection.
    
    Args:
        session_uuid: Session UUID
        next_action: Next action (drill_up, drill_down, keep_level_same)
        attempt_count: Number of attempts (for loop protection)
    """
    try:
        # Infinite loop protection
        MAX_ATTEMPTS = 10
        if attempt_count >= MAX_ATTEMPTS:
            logger.error(f"Maximum attempts ({MAX_ATTEMPTS}) reached for session {session_uuid}, ending interview")
            session = InterviewSession.objects.get(uuid=session_uuid)
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            # Update cumulative score when session is completed
            update_session_cumulative_score(session)
            
            if SessionManager.is_session_active(session_uuid):
                room_group_name = f'interview_{session_uuid}'
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'interview_completed',
                        'character': 'ai',
                        'message': 'Interview completed - maximum attempts reached'
                    }
                )
            return {'status': 'error', 'message': 'Maximum attempts reached'}
        
        logger.info(f"select_and_send_next_question called for session {session_uuid}, next_action: {next_action}, attempt: {attempt_count}")
        
        # Check if session is still active
        if not SessionManager.is_session_active(session_uuid):
            logger.warning(f"Session {session_uuid} is inactive, skipping question selection")
            return {'status': 'skipped', 'message': 'Session inactive'}
        
        session = InterviewSession.objects.get(uuid=session_uuid)
        logger.info(f"Session {session_uuid} - current_round: {session.current_round}, status: {session.status}, difficulty: {session.current_difficulty}")
        
        # Check if session has a valid candidate and panel
        if not session.interview_panel_candidate:
            logger.warning(f"Session {session_uuid} has no interview_panel_candidate - cannot select questions")
            return {'status': 'error', 'message': 'No candidate associated with session'}
        
        # Select next question with error handling
        try:
            logger.info(f"Selecting next question for session {session_uuid} with difficulty: {session.current_difficulty}")
            next_question_obj = question_selector.get_next_question(
                session, next_action, session.current_difficulty
            )
            logger.info(f"Next question selected: {next_question_obj}")
        except QuestionSelectionError as e:
            logger.error(f"Question selection failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
        if not next_question_obj:
            # No more questions available
            logger.warning(f"No more questions available for session {session_uuid}")
            # Only send completion if session is still active
            if SessionManager.is_session_active(session_uuid):
                room_group_name = f'interview_{session_uuid}'
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'interview_completed',
                        'character': 'ai',
                        'message': 'No more questions available'
                    }
                )
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            # Update cumulative score when session is completed
            update_session_cumulative_score(session)
            
            # Generate interview report
            logger.info(f"Triggering report generation for completed session {session_uuid}")
            generate_interview_report.delay(session_uuid)
            
            return {'status': 'completed', 'message': 'No more questions'}
        
        # Refresh question object to ensure we have latest data
        question = next_question_obj.question
        question.refresh_from_db()
        
        # Get question text - the Question model has 'question' field for the actual question text
        question_text = question.question.strip() if question.question else ""
        if not question_text:
            # Fallback to name if question field is empty
            question_text = question.name.strip() if question.name else ""
        if not question_text:
            # Final fallback
            question_text = "Please answer this question."
            logger.warning(f"Question {question.uuid} has no question text, using fallback")
        
        logger.info(f"Question text: {question_text[:100]}...")
        logger.info(f"Question name: {question.name}, Question field: {question.question[:50] if question.question else 'EMPTY'}...")
        
        # Create answer record for new question
        # Use atomic transaction to ensure round number consistency
        with transaction.atomic():
            session.refresh_from_db()  # Get latest round number
            new_round_number = session.current_round + 1
            
            new_answer = InterviewAnswer.objects.create(
                interview_session=session,
                question=next_question_obj,
                round_number=new_round_number,
                status='pending',
                started_at=timezone.now()
            )
            
            # Reset skip count for new answer
            from .audio_buffer import audio_buffer
            audio_buffer.reset_skip_count(str(new_answer.uuid))
            
            # Update session round and question index
            session.current_round = new_round_number
            session.current_question_index = F('current_question_index') + 1
            session.save()
            session.refresh_from_db()  # Refresh to get updated F() values
        
        # Prepare question data
        question_data = {
            'uuid': str(question.uuid),
            'name': question.name or '',
            'question': question.question or '',
            'description': question.description or '',
            'difficulty_level': question.difficulty_level,
            'expected_time_in_seconds': question.expected_time_in_seconds or 0,
            'category': question.category.name if question.category else None,
            'topic': question.topic.name if question.topic else None,
            'subtopic': question.subtopic.name if question.subtopic else None,
        }
        
        # Broadcast next question via WebSocket (only if session still active)
        if SessionManager.is_session_active(session_uuid):
            room_group_name = f'interview_{session_uuid}'
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'next_question',
                    'character': 'ai',
                    'message': question_text,  # Only the question text
                    'question_uuid': str(question.uuid),
                    'round_number': new_round_number,  # Use the round number we just created
                    'difficulty': session.current_difficulty,
                    # Include metadata separately if needed
                    'question_name': question.name or '',
                    'expected_time_in_seconds': question.expected_time_in_seconds or 0
                }
            )
        else:
            logger.warning(f"Session {session_uuid} became inactive before sending question")
        
        return {'status': 'success', 'question': question_data}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=2)
def generate_greeting(self, session_uuid):
    try:
        if not SessionManager.is_session_active(session_uuid):
            logger.warning(f"Session {session_uuid} is inactive, skipping greeting")
            return {'status': 'skipped', 'message': 'Session inactive'}
        
        session = InterviewSession.objects.get(uuid=session_uuid)
        if not session.interview_panel_candidate:
            return {'status': 'error', 'message': 'No candidate associated'}
        
        panel = session.interview_panel_candidate.interview_panel
        candidate_name = session.interview_panel_candidate.candidate.first_name

        try:
            greeting_text = greeting_service.generate_greeting(panel, candidate_name)
        except PromptInjectionError as e:
            logger.error(f"Prompt injection detected in greeting: {str(e)}")
            greeting_text = f"Welcome! Thank you for joining us for the {panel.name}. This is a voice-based interview, so please speak naturally and clearly. Let's begin!"
        except LLMServiceError as e:
            logger.error(f"LLM service error generating greeting: {str(e)}")
            greeting_text = f"Welcome! Thank you for joining us for the {panel.name}. This is a voice-based interview, so please speak naturally and clearly. Let's begin!"
        except Exception as e:
            logger.error(f"Unexpected error generating greeting: {str(e)}", exc_info=True)
            greeting_text = f"Welcome! Thank you for joining us for the {panel.name}. This is a voice-based interview, so please speak naturally and clearly. Let's begin!"
        
        session.greeting_text = greeting_text
        session.status = 'greeting'
        session.save()
        
        if SessionManager.is_session_active(session_uuid):
            room_group_name = f'interview_{session_uuid}'
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'greeting',
                    'character': 'ai',
                    'message': greeting_text,
                    'panel_name': panel.name,
                    'panel_description': panel.description
                }
            )
        
        return {'status': 'success', 'greeting': greeting_text}
    except InterviewSession.DoesNotExist:
        logger.warning(f"Session {session_uuid} not found")
        return {'status': 'error', 'message': 'Session not found'}
    except Exception as e:
        logger.error(f"Error generating greeting: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2)
        logger.warning("Greeting failed after retries, proceeding to first question")
        from .tasks import select_and_send_next_question
        select_and_send_next_question.delay(session_uuid, 'keep_level_same')
        return {'status': 'error', 'message': str(e), 'fallback': 'proceeded_to_question'}




@shared_task
def finalize_answer(answer_uuid, session_uuid):
    try:
        answer = InterviewAnswer.objects.get(uuid=answer_uuid)
        analyze_and_score_answer.delay(answer_uuid, session_uuid)
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def generate_answerwise_feedback(question_text, ideal_answer, candidate_answer, ollama_service):
    """Generate answer-wise feedback using AI comparing ideal answer with candidate answer"""
    try:
        sanitized_question = PromptSanitizer.sanitize_string(question_text, max_length=1000)
        sanitized_ideal = PromptSanitizer.sanitize_string(ideal_answer or "", max_length=2000)
        sanitized_candidate = PromptSanitizer.sanitize_transcription(candidate_answer or "")
        
        prompt = f"""You are an expert interviewer providing constructive feedback on a candidate's answer.

Question: {sanitized_question}

Ideal Answer: {sanitized_ideal}

Candidate's Answer: {sanitized_candidate}

Provide natural, balanced feedback that:
1. Highlights what the candidate did well
2. Points out areas for improvement in a constructive way
3. Compares their answer with the ideal answer
4. Provides specific, actionable feedback
5. Maintains a professional and encouraging tone

Do not only focus on negatives. Show both strengths and areas for improvement.
Write in a natural, conversational style as if you're providing feedback to help the candidate grow.

Return ONLY the feedback text, nothing else. No prefixes, no explanations."""
        
        data = {
            "model": ollama_service.model,
            "prompt": prompt,
            "stream": False
        }
        
        response = ollama_service._make_request("/api/generate", data)
        if response and 'response' in response:
            feedback = response['response'].strip()
            return feedback
        return "Feedback generation unavailable."
    except Exception as e:
        logger.error(f"Error generating answer-wise feedback: {str(e)}")
        return "Feedback generation encountered an error."


@shared_task
def generate_interview_report(session_uuid):
    """Generate PDF report for interview session with answer-wise feedback"""
    try:
        logger.info(f"Starting report generation for session {session_uuid} only")
        session = InterviewSession.objects.get(uuid=session_uuid)
        
        if not session.interview_panel_candidate:
            logger.error(f"No candidate associated with session {session_uuid}")
            return {'status': 'error', 'message': 'No candidate associated'}
        
        candidate = session.interview_panel_candidate.candidate
        panel = session.interview_panel_candidate.interview_panel
        
        logger.info(f"Generating report for candidate: {candidate.first_name} {candidate.last_name}, panel: {panel.name}, session: {session_uuid}")
        
        # Get all answered questions (exclude greeting round) - ensure we only get answers for THIS session
        answers = InterviewAnswer.objects.filter(
            interview_session=session,
            question__isnull=False,
            is_deleted=False
        ).select_related('question__question').order_by('round_number')
        
        if not answers.exists():
            logger.warning(f"No answers found for session {session_uuid}")
            return {'status': 'error', 'message': 'No answers found'}
        
        # Calculate/update cumulative score using helper function
        # Log all answer scores for debugging
        all_scores = [answer.score for answer in answers]
        logger.info(f"All answer scores for session {session_uuid}: {all_scores}")
        logger.info(f"Total answers: {len(answers)}, Answers with score > 0: {sum(1 for s in all_scores if s and s > 0)}")
        
        # Update cumulative score (will calculate if not already set)
        cumulative_score = update_session_cumulative_score(session)
        if cumulative_score is None:
            # Fallback calculation if helper function failed
            if all_scores:
                cumulative_score = sum(all_scores) / len(all_scores)
            else:
                cumulative_score = answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0.0
            cumulative_score = round(cumulative_score, 2)
            session.cumulative_score = cumulative_score
            session.save(update_fields=['cumulative_score'])
        
        logger.info(f"Final cumulative score for session {session_uuid}: {cumulative_score}/100")
        
        # Calculate competency scores
        technical_scores = []
        behavioral_scores = []
        psychological_scores = []
        
        for answer in answers:
            # Technical competency
            tech_score = (answer.score_technical or 0) + (answer.score_domain_knowledge or 0) + (answer.score_problem_solving or 0)
            technical_scores.append(tech_score)
            
            # Behavioral and soft skills competency
            behavioral_score = (
                (answer.score_communication or 0) + 
                (answer.score_creativity or 0) + 
                (answer.score_attention_to_detail or 0) + 
                (answer.score_time_management or 0) + 
                (answer.score_stress_management or 0) + 
                (answer.score_adaptability or 0) + 
                (answer.score_confidence or 0)
            )
            behavioral_scores.append(behavioral_score)
            
            # Psychological traits competency
            psychological_score = (answer.score_confidence or 0) + (answer.score_stress_management or 0)
            psychological_scores.append(psychological_score)
        
        avg_technical = sum(technical_scores) / len(technical_scores) if technical_scores else 0.0
        avg_behavioral = sum(behavioral_scores) / len(behavioral_scores) if behavioral_scores else 0.0
        avg_psychological = sum(psychological_scores) / len(psychological_scores) if psychological_scores else 0.0
        
        # Generate answer-wise feedback - optimized to reuse existing feedback
        # Only generate feedback for answers that don't have it yet
        answer_feedbacks = []
        feedbacks_to_generate = []
        
        # First pass: collect existing feedbacks and identify which need generation
        for answer in answers:
            question = answer.question.question
            ideal_answer = question.expected_answer or question.ideal_answer_summary or ""
            candidate_answer = answer.full_transcription or answer.transcription or ""
            
            # Check if feedback already exists
            existing_feedback = InterviewReportAnswerwiseFeedback.objects.filter(
                interview_session=session,
                answer=answer,
                is_deleted=False
            ).first()
            
            if existing_feedback and existing_feedback.feedback:
                feedback_text = existing_feedback.feedback
                logger.info(f"Using existing feedback for answer {answer.uuid}")
            else:
                # Mark for generation (only if candidate provided an answer)
                if candidate_answer and candidate_answer.strip():
                    feedbacks_to_generate.append({
                        'answer_uuid': str(answer.uuid),
                        'answer': answer,
                        'question_text': question.question,
                        'ideal_answer': ideal_answer,
                        'candidate_answer': candidate_answer
                    })
                    feedback_text = None  # Will be filled after generation
                else:
                    feedback_text = "No answer provided by candidate."
            
            answer_feedbacks.append({
                'answer_uuid': str(answer.uuid),
                'question': question.question,
                'candidate_answer': candidate_answer,
                'score': answer.score,
                'feedback': feedback_text,  # May be None if needs generation
                'round_number': answer.round_number
            })
        
        # Generate feedbacks only for answers that need it
        if feedbacks_to_generate:
            logger.info(f"Generating feedback for {len(feedbacks_to_generate)} answers (session {session_uuid} only)")
            ollama_service = OllamaService()
            
            # Generate feedback for each answer that needs it
            for feedback_data in feedbacks_to_generate:
                feedback_text = generate_answerwise_feedback(
                    feedback_data['question_text'],
                    feedback_data['ideal_answer'],
                    feedback_data['candidate_answer'],
                    ollama_service
                )
                
                # Save feedback to database
                InterviewReportAnswerwiseFeedback.objects.create(
                    interview_session=session,
                    answer=feedback_data['answer'],
                    feedback=feedback_text
                )
                
                # Update the answer_feedbacks list with generated feedback
                for af in answer_feedbacks:
                    if af['answer_uuid'] == feedback_data['answer_uuid']:
                        af['feedback'] = feedback_text
                        break
        
        # Build HTML for PDF
        candidate_name = html_escape.escape(f"{candidate.first_name} {candidate.last_name}".strip())
        candidate_email = html_escape.escape(candidate.email or "N/A")
        interview_start = session.started_at.strftime("%B %d, %Y at %I:%M %p") if session.started_at else "N/A"
        panel_name = html_escape.escape(panel.name)
        panel_description = html_escape.escape(panel.description or 'Technical interview assessment')
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                }}
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .header {{
                    text-align: center;
                    border-bottom: 3px solid #2c3e50;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                .header h1 {{
                    color: #2c3e50;
                    margin: 0;
                    font-size: 28px;
                }}
                .candidate-info {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 30px;
                }}
                .candidate-info h2 {{
                    color: #2c3e50;
                    margin-top: 0;
                    font-size: 20px;
                }}
                .candidate-info p {{
                    margin: 8px 0;
                    font-size: 14px;
                }}
                .panel-info {{
                    background-color: #e8f4f8;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 30px;
                }}
                .panel-info h3 {{
                    color: #2c3e50;
                    margin-top: 0;
                }}
                .competency-section {{
                    margin-bottom: 40px;
                    page-break-inside: avoid;
                }}
                .competency-header {{
                    background-color: #34495e;
                    color: white;
                    padding: 15px;
                    border-radius: 5px 5px 0 0;
                    margin-bottom: 0;
                }}
                .competency-content {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border: 1px solid #dee2e6;
                    border-top: none;
                    border-radius: 0 0 5px 5px;
                }}
                .score-display {{
                    display: inline-block;
                    background-color: #3498db;
                    color: white;
                    padding: 8px 15px;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .answer-section {{
                    margin-bottom: 30px;
                    page-break-inside: avoid;
                    border: 1px solid #dee2e6;
                    border-radius: 5px;
                    padding: 20px;
                    background-color: white;
                }}
                .answer-section h4 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                    margin-top: 0;
                }}
                .question-text {{
                    font-weight: bold;
                    color: #34495e;
                    margin-bottom: 10px;
                }}
                .candidate-answer {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-left: 4px solid #3498db;
                    margin: 15px 0;
                    font-style: italic;
                }}
                .feedback-text {{
                    background-color: #fff3cd;
                    padding: 15px;
                    border-left: 4px solid #ffc107;
                    margin: 15px 0;
                }}
                .cumulative-score {{
                    text-align: center;
                    background-color: #2c3e50;
                    color: white;
                    padding: 25px;
                    border-radius: 5px;
                    margin: 30px 0;
                }}
                .cumulative-score h2 {{
                    margin: 0;
                    font-size: 36px;
                }}
                .cumulative-score p {{
                    margin: 10px 0 0 0;
                    font-size: 18px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Interview Assessment Report</h1>
            </div>
            
            <div class="candidate-info">
                <h2>Candidate Information</h2>
                <p><strong>Name:</strong> {candidate_name}</p>
                <p><strong>Email:</strong> {candidate_email}</p>
                <p><strong>Interview Started:</strong> {interview_start}</p>
            </div>
            
            <div class="panel-info">
                <h3>Interview Panel: {panel_name}</h3>
                <p>{panel_description}</p>
            </div>
            
            <div class="cumulative-score">
                <h2>Cumulative Score: {cumulative_score}/100</h2>
                <p>Based on performance across all questions</p>
            </div>
            
            <div class="competency-section">
                <div class="competency-header">
                    <h3>Technical Competency</h3>
                </div>
                <div class="competency-content">
                    <p><strong>What is Technical Competency?</strong></p>
                    <p>Technical competency measures a candidate's understanding of core technical concepts, domain-specific knowledge, and problem-solving abilities. We assess how well candidates understand fundamental principles, apply technical knowledge to solve problems, and demonstrate expertise in their field.</p>
                    <p><strong>How we judge it:</strong> We evaluate technical competency by analyzing the depth of technical understanding, accuracy of domain knowledge, and effectiveness of problem-solving approaches. This includes assessing whether candidates can explain complex concepts clearly, identify appropriate solutions, and demonstrate practical technical skills.</p>
                    <div class="score-display">Average Score: {avg_technical:.2f}/3.0</div>
                </div>
            </div>
            
            <div class="competency-section">
                <div class="competency-header">
                    <h3>Behavioral and Soft Skills Competency</h3>
                </div>
                <div class="competency-content">
                    <p><strong>What is Behavioral and Soft Skills Competency?</strong></p>
                    <p>Behavioral and soft skills competency evaluates how candidates communicate, think creatively, pay attention to details, manage time, handle stress, adapt to situations, and demonstrate confidence. These skills are crucial for effective collaboration, leadership, and professional growth in any workplace.</p>
                    <p><strong>How we judge it:</strong> We assess these skills by observing communication clarity, creative thinking, attention to detail in responses, time management during answers, stress handling under pressure, adaptability to different question types, and overall confidence in delivery. These are measured through natural conversation patterns and response quality.</p>
                    <div class="score-display">Average Score: {avg_behavioral:.2f}/7.0</div>
                </div>
            </div>
            
            <div class="competency-section">
                <div class="competency-header">
                    <h3>Psychological Traits Competency</h3>
                </div>
                <div class="competency-content">
                    <p><strong>What is Psychological Traits Competency?</strong></p>
                    <p>Psychological traits competency focuses on a candidate's confidence level and ability to manage stress during challenging situations. These traits indicate how well candidates can perform under pressure and maintain composure during interviews.</p>
                    <p><strong>How we judge it:</strong> We evaluate psychological traits by observing confidence in responses, ability to handle difficult questions without becoming flustered, maintaining composure under pressure, and demonstrating self-assurance. This is assessed through voice tone, response quality, and how candidates handle unexpected or challenging questions.</p>
                    <div class="score-display">Average Score: {avg_psychological:.2f}/2.0</div>
                </div>
            </div>
            
            <h2 style="color: #2c3e50; margin-top: 40px; margin-bottom: 20px;">Answer-Wise Analysis</h2>
        """
        
        for idx, answer_data in enumerate(answer_feedbacks, 1):
            question_text = html_escape.escape(answer_data['question'])
            candidate_answer_text = html_escape.escape(answer_data['candidate_answer'] or 'No answer provided')
            feedback_text = html_escape.escape(answer_data['feedback'])
            # Replace newlines with <br> for proper formatting in PDF
            candidate_answer_text = candidate_answer_text.replace('\n', '<br>')
            feedback_text = feedback_text.replace('\n', '<br>')
            
            html_content += f"""
            <div class="answer-section">
                <h4>Question {idx} (Round {answer_data['round_number']})</h4>
                <div class="question-text">Q: {question_text}</div>
                <div class="candidate-answer">
                    <strong>Candidate's Answer:</strong><br>
                    {candidate_answer_text}
                </div>
                
                <div class="feedback-text">
                    <strong>Feedback:</strong><br>
                    {feedback_text}
                </div>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Create reports directory if it doesn't exist
        reports_dir = Path(settings.BASE_DIR) / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        # Generate PDF filename
        pdf_filename = f"interview_report_{session_uuid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = reports_dir / pdf_filename
        
        # Generate PDF
        HTML(string=html_content).write_pdf(pdf_path)
        
        # Save relative path to database
        relative_path = f"reports/{pdf_filename}"
        
        # Update session with PDF path and cumulative score
        session.report_pdf_path = relative_path
        session.cumulative_score = cumulative_score
        session.save()
        
        logger.info(f"Report generated successfully for session {session_uuid}: {relative_path}")
        
        return {
            'status': 'success',
            'pdf_path': relative_path,
            'cumulative_score': cumulative_score
        }
        
    except InterviewSession.DoesNotExist:
        logger.error(f"Session {session_uuid} not found")
        return {'status': 'error', 'message': 'Session not found'}
    except Exception as e:
        logger.error(f"Error generating report for session {session_uuid}: {str(e)}", exc_info=True)
        return {'status': 'error', 'message': str(e)}
