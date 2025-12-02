import base64
import json
import logging
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from .models import InterviewAnswer, InterviewSession, InterviewPanelQuestion, InterviewPanelCandidate
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
import os

logger = logging.getLogger(__name__)

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

