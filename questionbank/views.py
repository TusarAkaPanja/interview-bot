from rest_framework import status, permissions
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from utils.api_response import ApiResponseBuilder
from .models import Category, Topic, Subtopic, Question, QuestionConfiguration
from .serializers import (
    CategorySerializer, TopicSerializer, SubtopicSerializer,
    QuestionSerializer, QuestionGenerationRequestSerializer,
    QuestionConfigurationSerializer
)
from .question_generator import QuestionGenerator

import logging

logger = logging.getLogger(__name__)


# Custom pagination
class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response(data)



@method_decorator(csrf_exempt, name='dispatch')
class GenerateQuestionsView(APIView):
    """View for generating questions using Ollama"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate questions based on category, topic, and optional subtopic"""
        # can be done only by admin/superadmin
        if not request.user.role.name.lower() in ['admin', 'superadmin']:
            return ApiResponseBuilder.error(
                'Only admin and superadmin can generate questions',
                status_code=status.HTTP_403_FORBIDDEN
            )
        # Check if user has permission (admin or HR)
        if not request.user.role:
            return ApiResponseBuilder.error(
                'User must have a role to generate questions',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        role_name = request.user.role.name.lower()
        if role_name not in ['admin', 'hr']:
            return ApiResponseBuilder.error(
                'Only admin and HR users can generate questions',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request
        serializer = QuestionGenerationRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return ApiResponseBuilder.error(
                'Invalid request data',
                serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        
        # Get category, topic, and subtopic
        try:
            category = Category.objects.get(uuid=validated_data['category_uuid'])
            topic = Topic.objects.get(uuid=validated_data['topic_uuid'])
            subtopic = None
            if validated_data.get('subtopic_uuid'):
                subtopic = Subtopic.objects.get(uuid=validated_data['subtopic_uuid'])
        except (Category.DoesNotExist, Topic.DoesNotExist, Subtopic.DoesNotExist) as e:
            return ApiResponseBuilder.error(
                'Category, topic, or subtopic not found',
                str(e),
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Create question configuration (organization-specific)
        config_name = f"{category.name} > {topic.name}"
        if subtopic:
            config_name += f" > {subtopic.name}"
        config_name += f" ({validated_data['number_of_questions']} questions)"
        
        with transaction.atomic():
            config = QuestionConfiguration.objects.create(
                name=config_name,
                organization=request.user.organization,
                category=category,
                topic=topic,
                subtopic=subtopic,
                number_of_questions_to_generate=validated_data['number_of_questions'],
                number_of_questions_pending=validated_data['number_of_questions'],
                created_by=request.user,
                updated_by=request.user
            )
        
        # Start background generation
        generator = QuestionGenerator()
        generator.generate_questions_async(
            config_uuid=str(config.uuid),
            category_uuid=str(category.uuid),
            topic_uuid=str(topic.uuid),
            subtopic_uuid=str(subtopic.uuid) if subtopic else None,
            total_questions=validated_data['number_of_questions'],
            difficulty_partitions=validated_data['difficulty_partitions'],
            user=request.user
        )
        
        # Return configuration status
        config_serializer = QuestionConfigurationSerializer(config)
        return ApiResponseBuilder.success(
            'Question generation started successfully',
            config_serializer.data,
            status_code=status.HTTP_202_ACCEPTED
        )


@method_decorator(csrf_exempt, name='dispatch')
class QuestionConfigurationStatusView(APIView):
    """View to check question generation status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, config_uuid):
        """Get status of question generation"""
        try:
            config = QuestionConfiguration.objects.get(uuid=config_uuid)
            
            # Check if user has access (same organization)
            if config.organization != request.user.organization:
                return ApiResponseBuilder.error(
                    'You do not have access to this configuration',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            config_serializer = QuestionConfigurationSerializer(config)
            return ApiResponseBuilder.success(
                'Configuration status retrieved successfully',
                config_serializer.data
            )
        except QuestionConfiguration.DoesNotExist:
            return ApiResponseBuilder.error(
                'Configuration not found',
                status_code=status.HTTP_404_NOT_FOUND
            )


@method_decorator(csrf_exempt, name='dispatch')
class CategoryView(APIView):
    """View for category operations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create a new category"""
        serializer = CategorySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            category = serializer.save()
            return ApiResponseBuilder.success(
                'Category created successfully',
                CategorySerializer(category).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Category creation failed', serializer.errors)
    
    def get(self, request, category_id=None):
        """Get category details"""
        if category_id:
            try:
                category = Category.objects.get(uuid=category_id)
                return ApiResponseBuilder.success(
                    'Category retrieved successfully',
                    CategorySerializer(category).data
                )
            except Category.DoesNotExist:
                return ApiResponseBuilder.error(
                    'Category not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        return ApiResponseBuilder.error('Category ID required', status_code=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """Get all categories"""
        try:
            categories = Category.objects.all()
            return ApiResponseBuilder.success(
                'Categories retrieved successfully',
                CategorySerializer(categories, many=True).data
            )
        except Exception as e:
            return ApiResponseBuilder.error(
                'Error retrieving categories',
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, category_id):
        """Update category"""
        try:
            category = Category.objects.get(uuid=category_id)
            serializer = CategorySerializer(category, data=request.data, partial=True)
            if serializer.is_valid():
                category = serializer.save()
                return ApiResponseBuilder.success(
                    'Category updated successfully',
                    CategorySerializer(category).data
                )
            return ApiResponseBuilder.error('Category update failed', serializer.errors)
        except Category.DoesNotExist:
            return ApiResponseBuilder.error(
                'Category not found',
                status_code=status.HTTP_404_NOT_FOUND
            )


@method_decorator(csrf_exempt, name='dispatch')
class TopicView(APIView):
    """View for topic operations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create a new topic"""
        serializer = TopicSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            topic = serializer.save()
            return ApiResponseBuilder.success(
                'Topic created successfully',
                TopicSerializer(topic).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Topic creation failed', serializer.errors)
    
    def get(self, request, topic_uuid=None):
        """Get topic details"""
        if topic_uuid:
            try:
                topic = Topic.objects.get(uuid=topic_uuid)
                return ApiResponseBuilder.success(
                    'Topic retrieved successfully',
                    TopicSerializer(topic).data
                )
            except Topic.DoesNotExist:
                return ApiResponseBuilder.error(
                    'Topic not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        return ApiResponseBuilder.error('Topic ID required', status_code=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, topic_uuid):
        """Update topic"""
        try:
            topic = Topic.objects.get(uuid=topic_uuid)
            serializer = TopicSerializer(topic, data=request.data, partial=True)
            if serializer.is_valid():
                topic = serializer.save()
                return ApiResponseBuilder.success(
                    'Topic updated successfully',
                    TopicSerializer(topic).data
                )
            return ApiResponseBuilder.error('Topic update failed', serializer.errors)
        except Topic.DoesNotExist:
            return ApiResponseBuilder.error(
                'Topic not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

@method_decorator(csrf_exempt, name='dispatch')
class GetTopicsByCategoryView(APIView):
    """View for getting topics by category"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, category_uuid):
        """Get topics by category"""
        try:
            topics = Topic.objects.filter(category__uuid=category_uuid)
            return ApiResponseBuilder.success(
                message=f'{len(topics)} topics retrieved successfully for category {category_uuid}',
                data=TopicSerializer(topics, many=True).data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return ApiResponseBuilder.error(
                message=f'Error retrieving topics for category {category_uuid}',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class SubtopicView(APIView):
    """View for subtopic operations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create a new subtopic"""
        serializer = SubtopicSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            subtopic = serializer.save()
            return ApiResponseBuilder.success(
                'Subtopic created successfully',
                SubtopicSerializer(subtopic).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Subtopic creation failed', serializer.errors)
    
    def get(self, request, subtopic_uuid=None):
        """Get subtopic details"""
        if subtopic_uuid:
            try:
                subtopic = Subtopic.objects.get(uuid=subtopic_uuid)
                return ApiResponseBuilder.success(
                    'Subtopic retrieved successfully',
                    SubtopicSerializer(subtopic).data
                )
            except Subtopic.DoesNotExist:
                return ApiResponseBuilder.error(
                    'Subtopic not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        return ApiResponseBuilder.error('Subtopic ID required', status_code=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, subtopic_uuid):
        """Update subtopic"""
        try:
            subtopic = Subtopic.objects.get(uuid=subtopic_uuid)
            serializer = SubtopicSerializer(subtopic, data=request.data, partial=True)
            if serializer.is_valid():
                subtopic = serializer.save()
                return ApiResponseBuilder.success(
                    'Subtopic updated successfully',
                    SubtopicSerializer(subtopic).data
                )
            return ApiResponseBuilder.error('Subtopic update failed', serializer.errors)
        except Subtopic.DoesNotExist:
            return ApiResponseBuilder.error(
                'Subtopic not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

@method_decorator(csrf_exempt, name='dispatch')
class GetSubtopicsByTopicView(APIView):
    """View for getting subtopics by topic"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, topic_uuid):
        """Get subtopics by topic"""
        try:
            subtopics = Subtopic.objects.filter(topic__uuid=topic_uuid)
            return ApiResponseBuilder.success(
                message=f'{len(subtopics)} subtopics retrieved successfully for topic {topic_uuid}',
                data=SubtopicSerializer(subtopics, many=True).data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return ApiResponseBuilder.error(
                message=f'Error retrieving subtopics for topic {topic_uuid}',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class QuestionView(APIView):
    """View for question operations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create a new question"""
        # can be done only by admin/superadmin
        if not request.user.role.name.lower() in ['admin', 'superadmin']:
            return ApiResponseBuilder.error(
                'Only admin and superadmin can create questions',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = QuestionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.save()
            return ApiResponseBuilder.success(
                'Question created successfully',
                QuestionSerializer(question).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Question creation failed', serializer.errors)


    
    def get(self, request, question_uuid=None):
        """Get question details"""
        if question_uuid:
            try:
                question = Question.objects.get(uuid=question_uuid)
                return ApiResponseBuilder.success(
                    'Question retrieved successfully',
                    QuestionSerializer(question).data
                )
            except Question.DoesNotExist:
                return ApiResponseBuilder.error(
                    'Question not found',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        return ApiResponseBuilder.error('Question ID required', status_code=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, question_uuid):
        """Update question"""
        try:
            # can be done only by admin/superadmin
            if not request.user.role.name.lower() in ['admin', 'superadmin']:
                return ApiResponseBuilder.error(
                    'Only admin and superadmin can update questions',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            question = Question.objects.get(uuid=question_uuid)
            serializer = QuestionSerializer(question, data=request.data, partial=True)
            if serializer.is_valid():
                question = serializer.save()
                return ApiResponseBuilder.success(
                    'Question updated successfully',
                    QuestionSerializer(question).data
                )
            return ApiResponseBuilder.error('Question update failed', serializer.errors)
        except Question.DoesNotExist:
            return ApiResponseBuilder.error(
                'Question not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

# Get all questions with filteration and pagination
@method_decorator(csrf_exempt, name='dispatch')
class GetAllQuestionsView(APIView):
    """View for getting all questions with filteration and pagination"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get all questions with filteration and pagination"""
        try:
            # Optional filter parameters
            category_uuid = request.query_params.get('category_uuid', None)
            topic_uuid = request.query_params.get('topic_uuid', None)
            subtopic_uuid = request.query_params.get('subtopic_uuid', None)
            difficulty_level = request.query_params.get('difficulty_level', None)
            search = request.query_params.get('search', None)
            sort = request.query_params.get('sort', None)
            order = request.query_params.get('order', None)
            
            page = request.query_params.get('page', '1')
            page_size = request.query_params.get('page_size', '10')
            filter_kwargs = {}
            if category_uuid:
                filter_kwargs['category__uuid'] = category_uuid
            if topic_uuid:
                filter_kwargs['topic__uuid'] = topic_uuid
            if subtopic_uuid:
                filter_kwargs['subtopic__uuid'] = subtopic_uuid
            if difficulty_level:
                filter_kwargs['difficulty_level'] = difficulty_level
            if search:
                filter_kwargs['question__icontains'] = search

            questions = Question.objects.filter(**filter_kwargs)
            
            # Apply sorting
            if sort:
                if order and order.lower() == 'desc':
                    sort = f'-{sort}'
                questions = questions.order_by(sort)
            elif order:
                questions = questions.order_by(order)

            paginator = CustomPagination()
            paginated_questions = paginator.paginate_queryset(questions, request)
            return paginator.get_paginated_response(QuestionSerializer(paginated_questions, many=True).data)
        except Exception as e:
            return ApiResponseBuilder.error(
                message='Error retrieving questions',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )