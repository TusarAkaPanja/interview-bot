import json
import base64
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .turn_detection import turn_detector
from .session_manager import SessionManager
from .audio_buffer import audio_buffer
from .tasks import process_buffered_audio
from .models import InterviewPanelCandidate, InterviewSession, InterviewAnswer, InterviewPanelQuestion
from .tasks import finalize_answer
import time

logger = logging.getLogger(__name__)


class InterviewConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.interview_panel_candidate = None
        self.interview_session = None
        self.room_group_name = None
        self.question_uuid = None

    async def connect(self):
        self.token = self.scope['url_route']['kwargs']['token']
        
        # TODO: Re-enable validation after testing
        # Validate token and get interview panel candidate
        # self.interview_panel_candidate = await self.get_interview_panel_candidate()
        # 
        # if not self.interview_panel_candidate:
        #     await self.close(code=4001)
        #     return
        # 
        # # Check if panel is active
        # if not await self.is_panel_active():
        #     await self.close(code=4002)
        #     return
        
        # TODO: For testing: Try to get candidate, but don't fail if not found
        self.interview_panel_candidate = await self.get_interview_panel_candidate()
        self.interview_session = await self.get_or_create_session()
        
        # TODO:For testing: Create a mock session UUID if no session
        import uuid
        if not self.interview_session:
            mock_uuid = uuid.uuid4()
            self.room_group_name = f'interview_{mock_uuid}'
            session_uuid = str(mock_uuid)
            question_index = 0
        else:
            self.room_group_name = f'interview_{self.interview_session.uuid}'
            session_uuid = str(self.interview_session.uuid)
            question_index = self.interview_session.current_question_index
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connection established',
            'session_uuid': session_uuid,
            'current_question_index': question_index
        }))
        
        # Generate greeting
        if self.interview_session:
            from .tasks import generate_greeting
            generate_greeting.delay(session_uuid)

    async def disconnect(self, close_code):
        if self.interview_session:
            audio_buffer.flush_session(str(self.interview_session.uuid))
            audio_buffer.cleanup_session(str(self.interview_session.uuid))
            SessionManager.mark_session_inactive(str(self.interview_session.uuid))
        
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            logger.info(f"Received audio chunk: {bytes_data}")
            await self.handle_audio_chunk(bytes_data)
        elif text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get('type')
                
                if message_type == 'skip_question':
                    await self.handle_skip_question()
                elif message_type == 'end_interview':
                    await self.handle_end_interview()
                elif message_type == 'end_round':
                    await self.handle_end_round()
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Unknown message type'
                    }))
            except json.JSONDecodeError:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))

    async def handle_audio_chunk(self, audio_data):
        if not self.interview_session:
            return
        current_answer = await self.get_current_answer()
        if not current_answer:
            return
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
       
        buffered = audio_buffer.add_chunk(
            session_uuid=str(self.interview_session.uuid),
            answer_uuid=str(current_answer.uuid),
            audio_base64=audio_base64,
            chunk_timestamp=time.time()
        )
        
        turn_detector.update_audio(
            str(self.interview_session.uuid), 
            has_speech=True, 
            chunk_received=True
        )
        if buffered:
            process_buffered_audio.delay(
                answer_uuid=buffered['answer_uuid'],
                audio_chunks=buffered['audio_chunks'],
                session_uuid=str(self.interview_session.uuid)
            )
    

    async def handle_skip_question(self):
        """Handle question skip"""
        current_answer = await self.get_current_answer()
        if current_answer:
            await self.update_answer_status(current_answer, 'skipped')
            finalize_answer.delay(str(current_answer.uuid), str(self.interview_session.uuid))

    async def handle_end_round(self):
        """Handle end of round - finalize current answer"""
        if not self.interview_session:
            return
        
        turn_detector.end_turn(str(self.interview_session.uuid))
        
        current_answer = await self.get_current_answer()
        if current_answer:
            from .tasks import finalize_answer
            finalize_answer.delay(str(current_answer.uuid), str(self.interview_session.uuid))
            
    async def handle_end_interview(self):
        """Handle interview completion"""
        if self.interview_session:
            await self.update_session_status('completed')
            await self.send(text_data=json.dumps({
                'type': 'interview_completed',
                'message': 'Interview completed successfully'
            }))


    async def transcription_update(self, event):
        """Handle transcription update from task (real-time display only, no analysis)"""
        await self.send(text_data=json.dumps({
            'type': 'transcription_update',
            'character': event.get('character', 'candidate'),
            'message': event.get('message', event.get('transcription', '')),
            'answer_uuid': event.get('answer_uuid'),
            'is_partial': event.get('is_partial', False) 
        }))
        
        if self.interview_session:
            turn_detector.update_audio(
                str(self.interview_session.uuid), 
                has_speech=True, 
                chunk_received=False
            )

    async def scoring_update(self, event):
        """Handle scoring update from task"""
        await self.send(text_data=json.dumps({
            'type': 'scoring_update',
            'character': event.get('character', 'ai'),
            'score': event['score'],
            'answer_uuid': event.get('answer_uuid'),
            'summary': event.get('summary', ''),
            'next_action': event.get('next_action', 'keep_level_same')
        }))

    async def greeting(self, event):
        await self.send(text_data=json.dumps({
            'type': 'greeting',
            'character': event.get('character', 'ai'),
            'message': event.get('message', event.get('greeting', '')),
            'panel_name': event.get('panel_name', ''),
            'panel_description': event.get('panel_description', '')
        }))
        
        if self.interview_session:
            from .tasks import select_and_send_next_question
            select_and_send_next_question.delay(
                str(self.interview_session.uuid),
                'keep_level_same'
            )

    async def next_question(self, event):
        """Handle next question from task"""
        await self.send(text_data=json.dumps({
            'type': 'next_question',
            'character': event.get('character', 'ai'),
            'message': event.get('message', ''),  # Only question text
            'question_uuid': event.get('question_uuid', ''),
            'round_number': event.get('round_number', 0),
            'difficulty': event.get('difficulty', 'easy'),
            'question_name': event.get('question_name', ''),
            'expected_time_in_seconds': event.get('expected_time_in_seconds', 0)
        }))
        
        # Start turn detection for new question (async-safe)
        if self.interview_session:
            await self.start_turn_detection()
            # Start periodic timeout check (must be in async context)
            asyncio.create_task(self._periodic_timeout_check())
    
    @database_sync_to_async
    def start_turn_detection(self):
        if not self.interview_session:
            return
        
        current_answer = SessionManager.get_current_answer(self.interview_session)
        if current_answer:            
            turn_detector.start_turn(
                str(self.interview_session.uuid),
                str(current_answer.uuid),
            )

    async def interview_completed(self, event):
        """Handle interview completion message from task"""
        await self.send(text_data=json.dumps({
            'type': 'interview_completed',
            'character': event.get('character', 'ai'),
            'message': event.get('message', 'Interview completed successfully')
        }))

    
    @database_sync_to_async
    def check_session_has_candidate(self):
        """Check if session has a valid candidate (async-safe)"""
        if not self.interview_session:
            return False
        try:
            self.interview_session.refresh_from_db()
            return self.interview_session.interview_panel_candidate is not None
        except Exception:
            return False

    async def _periodic_timeout_check(self):
        if not self.interview_session:
            return
        
        session_uuid = str(self.interview_session.uuid)
        
        while True:
            try:
                await asyncio.sleep(1)
                
                if not self.interview_session:
                    break
                
                end_turn = turn_detector.update_audio(session_uuid, has_speech=False, chunk_received=False)
                
                if end_turn:
                    reason = end_turn.get('reason', 'unknown')
                    logger.info(f"Timeout detected for session {session_uuid}: {reason}")

                    await self.handle_end_round()
                    break
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic timeout check: {str(e)}")
                break
    
    @database_sync_to_async
    def get_interview_panel_candidate(self):
        try:
            return InterviewPanelCandidate.objects.select_related(
                'interview_panel', 'candidate'
            ).get(
                token=self.token,
                is_deleted=False,
                is_active=True
            )
        except InterviewPanelCandidate.DoesNotExist:
            return None

    @database_sync_to_async
    def is_panel_active(self):
        if not self.interview_panel_candidate:
            return False
        panel = self.interview_panel_candidate.interview_panel
        now = timezone.now()
        return panel.is_active and panel.start_datetime <= now <= panel.end_datetime

    @database_sync_to_async
    def get_or_create_session(self):
        # TODO: For testing: Allow connection even without valid candidate
        if not self.interview_panel_candidate:
            return None
        
        session, created = InterviewSession.objects.get_or_create(
            interview_panel_candidate=self.interview_panel_candidate,
            is_deleted=False,
            defaults={
                'status': 'pending',
                'started_at': timezone.now(),
                'current_difficulty': 'easy'
            }
        )
        if created:
            session.status = 'pending'
            session.started_at = timezone.now()
            session.current_difficulty = 'easy'
            # Calculate total questions available
            if self.interview_panel_candidate:
                session.total_questions_available = InterviewPanelQuestion.objects.filter(
                    interview_panel=self.interview_panel_candidate.interview_panel,
                    is_deleted=False,
                    is_active=True
                ).count()
            logger.info(f"Total questions available: {session.total_questions_available}")
            logger.info(f"Session created: {session.id}")
            logger.info(f"Session status: {session.status}")
            session.save()
        return session

    @database_sync_to_async
    def get_current_answer(self):
        try:
            if not self.interview_session:
                return None
            
            return SessionManager.get_current_answer(self.interview_session)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting current answer: {str(e)}")
            return None

    @database_sync_to_async
    def update_answer_status(self, answer, status):
        answer.status = status
        if status == 'skipped':
            answer.answered_at = timezone.now()
        answer.save()

    @database_sync_to_async
    def increment_question_index(self):
        self.interview_session.current_question_index += 1
        self.interview_session.save()

    @database_sync_to_async
    def update_session_status(self, status):
        self.interview_session.status = status
        if status == 'completed':
            self.interview_session.completed_at = timezone.now()
        self.interview_session.save()

    @database_sync_to_async
    def refresh_session(self):
        """Refresh session from database"""
        self.interview_session.refresh_from_db()

    @database_sync_to_async
    def get_total_questions(self):
        # For testing: Return 0 if no candidate
        if not self.interview_panel_candidate:
            return 0
        return InterviewPanelQuestion.objects.filter(
            interview_panel=self.interview_panel_candidate.interview_panel,
            is_deleted=False,
            is_active=True
        ).count()

    

