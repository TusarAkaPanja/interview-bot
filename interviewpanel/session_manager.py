"""
Session state management to prevent race conditions and handle disconnects.
"""
import logging
import time
from typing import Optional, Dict
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from .models import InterviewSession, InterviewAnswer, InterviewPanelQuestion

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages interview session state with proper locking and sequencing"""
    
    @staticmethod
    @transaction.atomic
    def get_current_answer(session: InterviewSession) -> Optional[InterviewAnswer]:
        try:
            session.refresh_from_db()
            current_answer = InterviewAnswer.objects.select_for_update().filter(
                interview_session=session,
                round_number=session.current_round,
                is_deleted=False,
                status__in=['pending', 'analyzing']
            ).first()
            
            return current_answer
            
        except Exception as e:
            logger.error(f"Error getting current answer: {str(e)}")
            return None
    
    @staticmethod
    @transaction.atomic
    def increment_round(session: InterviewSession) -> bool:
        try:
            updated = InterviewSession.objects.filter(
                id=session.id,
                current_round=session.current_round
            ).update(
                current_round=F('current_round') + 1,
                questions_asked_count=F('questions_asked_count') + 1
            )
            
            if updated > 0:
                session.refresh_from_db()
                return True
            else:
                logger.warning(f"Failed to increment round for session {session.uuid} - possible race condition")
                return False
                
        except Exception as e:
            logger.error(f"Error incrementing round: {str(e)}")
            return False
    
    @staticmethod
    def get_question_by_round(
        session: InterviewSession,
        round_number: int
    ) -> Optional[InterviewPanelQuestion]:
        try:
            answer = InterviewAnswer.objects.filter(
                interview_session=session,
                round_number=round_number,
                is_deleted=False
            ).select_related('question__question').first()
            
            if answer and answer.question:
                return answer.question
            
            return None
        except Exception as e:
            logger.error(f"Error getting question by round: {str(e)}")
            return None
    
    @staticmethod
    def mark_session_inactive(session_uuid: str):
        try:
            InterviewSession.objects.filter(
                uuid=session_uuid
            ).update(is_active=False)
            logger.info(f"Marked session {session_uuid} as inactive")
        except Exception as e:
            logger.error(f"Error marking session inactive: {str(e)}")
    
    @staticmethod
    def is_session_active(session_uuid: str) -> bool:
        try:
            return InterviewSession.objects.filter(
                uuid=session_uuid,
                is_active=True
            ).exists()
        except Exception:
            return False

