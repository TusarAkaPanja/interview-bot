from rest_framework import status, permissions
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from django.utils import timezone
from django.http import FileResponse
from django.conf import settings
from pathlib import Path
import random
from utils.api_response import ApiResponseBuilder
from organizations.permissions import IsAdminOrHr
from .models import InterviewPanel, InterviewPanelQuestionDistribution, InterviewPanelQuestion, InterviewPanelCandidate, InterviewSession, InterviewAnswer, InterviewReportAnswerwiseFeedback
from .serializers import InterviewPanelCreateSerializer, InterviewPanelUpdateSerializer, InterviewPanelSerializer
from questionbank.models import Category, Topic, Subtopic, Question
from authentication.models import Candidate

@method_decorator(csrf_exempt, name='dispatch')
class InterviewPanelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrHr]
    
    def post(self, request):        
        role_name = request.user.role.name.lower()
        if role_name not in ['admin', 'hr']:
            return ApiResponseBuilder.error(
                'Only admin and HR users can create interview panels',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = InterviewPanelCreateSerializer(
            data=request.data,
            context={'request': request, 'organization': request.user.organization}
        )
        
        if not serializer.is_valid():
            return ApiResponseBuilder.error(
                'Invalid request data',
                serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        
        try:
            category = Category.objects.get(uuid=validated_data['category_uuid'])
        except Category.DoesNotExist:
            return ApiResponseBuilder.error(
                'Category not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        with transaction.atomic():
            interview_panel = InterviewPanel.objects.create(
                name=validated_data['name'],
                description=validated_data.get('description', ''),
                total_number_of_questions=validated_data['total_number_of_questions'],
                start_datetime=validated_data['start_datetime'],
                end_datetime=validated_data['end_datetime'],
                organization=request.user.organization,
                created_by=request.user,
                updated_by=request.user
            )
            
            for dist_data in validated_data['question_distributions']:
                topic = Topic.objects.get(uuid=dist_data['topic_uuid'])
                subtopic = Subtopic.objects.get(uuid=dist_data['subtopic_uuid'])
                
                total_questions = dist_data['easy'] + dist_data['medium'] + dist_data['hard']
                
                question_distribution = InterviewPanelQuestionDistribution.objects.create(
                    interview_panel=interview_panel,
                    category=category,
                    topic=topic,
                    subtopic=subtopic,
                    number_of_questions=total_questions,
                    number_of_easy_questions=dist_data['easy'],
                    number_of_medium_questions=dist_data['medium'],
                    number_of_hard_questions=dist_data['hard'],
                    created_by=request.user,
                    updated_by=request.user
                )
                existing_question_ids = set(
                    InterviewPanelQuestion.objects.filter(
                        interview_panel=interview_panel
                    ).values_list('question_id', flat=True)
                )
                
                if dist_data['easy'] > 0:
                    easy_questions = list(Question.objects.filter(
                        category=category,
                        topic=topic,
                        subtopic=subtopic,
                        difficulty_level='easy'
                    ).exclude(id__in=existing_question_ids).values_list('id', flat=True))
                    
                    available_easy_count = len(easy_questions)
                    if available_easy_count > 0:
                        num_to_select = min(dist_data['easy'], available_easy_count)
                        selected_easy = random.sample(easy_questions, num_to_select)
                        for question_id in selected_easy:
                            InterviewPanelQuestion.objects.create(
                                interview_panel=interview_panel,
                                question_id=question_id,
                                created_by=request.user,
                                updated_by=request.user
                            )
                            existing_question_ids.add(question_id)
                
                if dist_data['medium'] > 0:
                    medium_questions = list(Question.objects.filter(
                        category=category,
                        topic=topic,
                        subtopic=subtopic,
                        difficulty_level='medium'
                    ).exclude(id__in=existing_question_ids).values_list('id', flat=True))
                    
                    available_medium_count = len(medium_questions)
                    if available_medium_count > 0:
                        num_to_select = min(dist_data['medium'], available_medium_count)
                        selected_medium = random.sample(medium_questions, num_to_select)
                        
                        for question_id in selected_medium:
                            InterviewPanelQuestion.objects.create(
                                interview_panel=interview_panel,
                                question_id=question_id,
                                created_by=request.user,
                                updated_by=request.user
                            )
                            existing_question_ids.add(question_id)
                
                if dist_data['hard'] > 0:
                    hard_questions = list(Question.objects.filter(
                        category=category,
                        topic=topic,
                        subtopic=subtopic,
                        difficulty_level='hard'
                    ).exclude(id__in=existing_question_ids).values_list('id', flat=True))
                    
                    available_hard_count = len(hard_questions)
                    if available_hard_count > 0:
                        num_to_select = min(dist_data['hard'], available_hard_count)
                        selected_hard = random.sample(hard_questions, num_to_select)
                        
                        for question_id in selected_hard:
                            InterviewPanelQuestion.objects.create(
                                interview_panel=interview_panel,
                                question_id=question_id,
                                created_by=request.user,
                                updated_by=request.user
                            )
                            existing_question_ids.add(question_id)
            
            candidate_uuids = validated_data.get('candidate_uuids', [])
            for candidate_uuid in candidate_uuids:
                try:
                    candidate = Candidate.objects.get(uuid=candidate_uuid, organization=request.user.organization)
                    panel_candidate = InterviewPanelCandidate.objects.create(
                        interview_panel=interview_panel,
                        candidate=candidate
                    )
                    panel_candidate.generate_token()
                except Candidate.DoesNotExist:
                    continue
        
        interview_panel.check_and_deactivate()
        
        return ApiResponseBuilder.success(
            'Interview panel created successfully',
            InterviewPanelSerializer(interview_panel).data,
            status_code=status.HTTP_201_CREATED
        )
    
    def get(self, request, interview_panel_uuid=None, **kwargs):
        if not request.user.organization:
            return ApiResponseBuilder.error(
                'User must belong to an organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        interview_panel_uuid = interview_panel_uuid or kwargs.get('interview_panel_uuid')
        
        if interview_panel_uuid:
            try:
                interview_panel = InterviewPanel.objects.get(
                    uuid=interview_panel_uuid,
                    organization=request.user.organization,
                    is_deleted=False
                )
                interview_panel.check_and_deactivate()
                interview_panel.refresh_from_db()
                
                return ApiResponseBuilder.success(
                    'Interview panel retrieved successfully',
                    InterviewPanelSerializer(interview_panel).data
                )
            except InterviewPanel.DoesNotExist:
                return ApiResponseBuilder.error(
                    'Interview panel not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        else:
            interview_panels = InterviewPanel.objects.filter(
                organization=request.user.organization,
                is_deleted=False
            ).order_by('-created_at')
            
            for panel in interview_panels:
                panel.check_and_deactivate()
            
            interview_panels = InterviewPanel.objects.filter(
                organization=request.user.organization,
                is_deleted=False
            ).order_by('-created_at')
            
            serializer = InterviewPanelSerializer(interview_panels, many=True)
            return ApiResponseBuilder.success(
                'Interview panels retrieved successfully',
                {'interview_panels': serializer.data}
            )
    
    def put(self, request, interview_panel_uuid=None, **kwargs):
        interview_panel_uuid = interview_panel_uuid or kwargs.get('interview_panel_uuid')
        
        if not interview_panel_uuid:
            return ApiResponseBuilder.error(
                'Interview panel UUID is required',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.role:
            return ApiResponseBuilder.error(
                'User must have a role',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        role_name = request.user.role.name.lower()
        if role_name not in ['admin', 'hr']:
            return ApiResponseBuilder.error(
                'Only admin and HR users can update interview panels',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            interview_panel = InterviewPanel.objects.get(
                uuid=interview_panel_uuid,
                organization=request.user.organization,
                is_deleted=False
            )
        except InterviewPanel.DoesNotExist:
            return ApiResponseBuilder.error(
                'Interview panel not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        interview_panel.check_and_deactivate()
        interview_panel.refresh_from_db()
        
        if not interview_panel.is_active:
            return ApiResponseBuilder.error(
                'Cannot update inactive interview panel',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = InterviewPanelUpdateSerializer(
            interview_panel,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return ApiResponseBuilder.error(
                'Invalid request data',
                serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save(updated_by=request.user)
        interview_panel.refresh_from_db()
        interview_panel.check_and_deactivate()
        
        return ApiResponseBuilder.success(
            'Interview panel updated successfully',
            InterviewPanelSerializer(interview_panel).data
        )
    
    def delete(self, request, interview_panel_uuid=None, **kwargs):
        interview_panel_uuid = interview_panel_uuid or kwargs.get('interview_panel_uuid')
        
        if not interview_panel_uuid:
            return ApiResponseBuilder.error(
                'Interview panel UUID is required',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.role:
            return ApiResponseBuilder.error(
                'User must have a role',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        role_name = request.user.role.name.lower()
        if role_name not in ['admin', 'hr']:
            return ApiResponseBuilder.error(
                'Only admin and HR users can delete interview panels',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            interview_panel = InterviewPanel.objects.get(
                uuid=interview_panel_uuid,
                organization=request.user.organization,
                is_deleted=False
            )
        except InterviewPanel.DoesNotExist:
            return ApiResponseBuilder.error(
                'Interview panel not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        interview_panel.is_deleted = True
        interview_panel.save()
        
        return ApiResponseBuilder.success(
            'Interview panel deleted successfully'
        )

@method_decorator(csrf_exempt, name='dispatch')
class StartInterviewPanelView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            interview_panel_candidate = InterviewPanelCandidate.objects.get(token=token)
            username = request.data.get('username')
            password = request.data.get('password')
            
            if not username or not password:
                return ApiResponseBuilder.error(
                    'Username and password are required',
                    status_code=status.HTTP_400_BAD_REQUEST)
            
            candidate = interview_panel_candidate.candidate
            
            if candidate.email != username:
                return ApiResponseBuilder.error(
                    'Invalid username or password',
                    status_code=status.HTTP_401_UNAUTHORIZED)
            
            if candidate.organization != interview_panel_candidate.interview_panel.organization:
                return ApiResponseBuilder.error(
                    'Candidate not found',
                    status_code=status.HTTP_404_NOT_FOUND)
            
            if not candidate.check_password(password):
                return ApiResponseBuilder.error(
                    'Invalid username or password',
                    status_code=status.HTTP_401_UNAUTHORIZED)
            if interview_panel_candidate.interview_panel.start_datetime > timezone.now():
                return ApiResponseBuilder.error(
                    'Interview panel has not started yet',
                    status_code=status.HTTP_400_BAD_REQUEST)
            if interview_panel_candidate.interview_panel.end_datetime < timezone.now():
                return ApiResponseBuilder.error(
                    'Interview panel has ended',
                    status_code=status.HTTP_400_BAD_REQUEST)
            
            return ApiResponseBuilder.success(
                'Interview panel started successfully',
                status_code=status.HTTP_200_OK)
        except InterviewPanelCandidate.DoesNotExist:
            return ApiResponseBuilder.error(
                'Invalid token',
                status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ApiResponseBuilder.error(
                'Error starting interview panel',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class CandidateReportDetailView(APIView):
    """API to get detailed report data for UI display for admin/recruiter"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrHr]

    def get(self, request, session_uuid):
        """Get detailed report data for a completed interview session"""
        if not request.user.organization:
            return ApiResponseBuilder.error(
                'User must belong to an organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            session = InterviewSession.objects.get(
                uuid=session_uuid,
                is_deleted=False
            )
            
            if not session.interview_panel_candidate:
                return ApiResponseBuilder.error(
                    'No candidate associated with this session',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Check organization access
            if session.interview_panel_candidate.interview_panel.organization != request.user.organization:
                return ApiResponseBuilder.error(
                    'Access denied',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            if session.status != 'completed':
                return ApiResponseBuilder.error(
                    'Interview session is not completed yet',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            candidate = session.interview_panel_candidate.candidate
            panel = session.interview_panel_candidate.interview_panel
            
            # Get all answers
            answers = InterviewAnswer.objects.filter(
                interview_session=session,
                question__isnull=False,
                is_deleted=False
            ).select_related('question__question').order_by('round_number')
            
            # Calculate competency scores
            technical_scores = []
            behavioral_scores = []
            psychological_scores = []
            
            answer_data_list = []
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
                
                # Get feedback
                feedback_obj = InterviewReportAnswerwiseFeedback.objects.filter(
                    interview_session=session,
                    answer=answer,
                    is_deleted=False
                ).first()
                
                answer_data_list.append({
                    'question': answer.question.question.question,
                    'candidate_answer': answer.full_transcription or answer.transcription or 'No answer provided',
                    'score': answer.score,
                    'feedback': feedback_obj.feedback if feedback_obj else 'No feedback available',
                    'round_number': answer.round_number
                })
            
            avg_technical = sum(technical_scores) / len(technical_scores) if technical_scores else 0.0
            avg_behavioral = sum(behavioral_scores) / len(behavioral_scores) if behavioral_scores else 0.0
            avg_psychological = sum(psychological_scores) / len(psychological_scores) if psychological_scores else 0.0
            
            report_data = {
                'session_uuid': str(session.uuid),
                'candidate_name': f"{candidate.first_name} {candidate.last_name}",
                'candidate_email': candidate.email,
                'interview_panel_name': panel.name,
                'interview_panel_description': panel.description,
                'started_at': session.started_at,
                'completed_at': session.completed_at,
                'cumulative_score': session.cumulative_score,
                'technical_competency_score': round(avg_technical, 2),
                'behavioral_competency_score': round(avg_behavioral, 2),
                'psychological_competency_score': round(avg_psychological, 2),
                'answers': answer_data_list
            }
            
            return ApiResponseBuilder.success(
                'Report data retrieved successfully',
                report_data
            )
        except InterviewSession.DoesNotExist:
            return ApiResponseBuilder.error(
                'Interview session not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ApiResponseBuilder.error(
                'Error retrieving report data',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class CandidateReportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrHr]

    def get(self, request, session_uuid):
        if not request.user.organization:
            return ApiResponseBuilder.error(
                'User must belong to an organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            session = InterviewSession.objects.get(
                uuid=session_uuid,
                is_deleted=False
            )
            
            if not session.interview_panel_candidate:
                return ApiResponseBuilder.error(
                    'No candidate associated with this session',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Check organization access
            if session.interview_panel_candidate.interview_panel.organization != request.user.organization:
                return ApiResponseBuilder.error(
                    'Access denied',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            if session.status != 'completed':
                return ApiResponseBuilder.error(
                    'Interview session is not completed yet',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            if not session.report_pdf_path:
                return ApiResponseBuilder.error(
                    'Report PDF not available',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Build full path to PDF
            pdf_path = Path(settings.BASE_DIR) / session.report_pdf_path
            
            if not pdf_path.exists():
                return ApiResponseBuilder.error(
                    'Report PDF file not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Return file response
            return FileResponse(
                open(pdf_path, 'rb'),
                content_type='application/pdf',
                filename=pdf_path.name
            )
        except InterviewSession.DoesNotExist:
            return ApiResponseBuilder.error(
                'Interview session not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ApiResponseBuilder.error(
                'Error downloading report',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)