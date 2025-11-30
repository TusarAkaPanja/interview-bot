from django.urls import path
from .views import (
    CategoryView, TopicView, SubtopicView, QuestionView,
    GenerateQuestionsView, QuestionConfigurationStatusView, GetTopicsByCategoryView, GetSubtopicsByTopicView,
    GetAllQuestionsView, GetAllQuestionConfigurationsView
)

app_name = 'questionbank'

urlpatterns = [
    # Category endpoints
    path('create-category/', CategoryView.as_view(), name='create_category'),
    path('get-categories/', CategoryView.as_view(), name='get_categories'),
    path('get-category/<str:category_uuid>/', CategoryView.as_view(), name='get_category'),
    path('update-category/<str:category_uuid>/', CategoryView.as_view(), name='update_category'),
    
    # Topic endpoints
    path('create-topic/', TopicView.as_view(), name='create_topic'),
    path('get-topic/<str:topic_uuid>/', TopicView.as_view(), name='get_topic'),
    path('update-topic/<str:topic_uuid>/', TopicView.as_view(), name='update_topic'),
    path('get-topics-by-category/<str:category_uuid>/', GetTopicsByCategoryView.as_view(), name='get_topics_by_category'),
    
    # Subtopic endpoints
    path('create-subtopic/', SubtopicView.as_view(), name='create_subtopic'),
    path('get-subtopic/<str:subtopic_uuid>/', SubtopicView.as_view(), name='get_subtopic'),
    path('update-subtopic/<str:subtopic_uuid>/', SubtopicView.as_view(), name='update_subtopic'),
    path('get-subtopics-by-topic/<str:topic_uuid>/', GetSubtopicsByTopicView.as_view(), name='get_subtopics_by_topic'),
    
    # Question endpoints
    path('create-question/', QuestionView.as_view(), name='create_question'),
    path('get-question/<str:question_uuid>/', QuestionView.as_view(), name='get_question'),
    path('update-question/<str:question_uuid>/', QuestionView.as_view(), name='update_question'),
    path('get-all-questions/', GetAllQuestionsView.as_view(), name='get_all_questions'),
    
    # Question generation endpoints
    path('generate-questions/', GenerateQuestionsView.as_view(), name='generate_questions'),
    path('question-configuration-status/<str:config_uuid>/', QuestionConfigurationStatusView.as_view(), name='question_configuration_status'),
    path('get-all-question-configurations/', GetAllQuestionConfigurationsView.as_view(), name='get_all_question_configurations'),
]

