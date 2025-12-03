from django.urls import path
from .views import (
    InterviewPanelView,
    StartInterviewPanelView,
    CandidateReportDetailView,
    CandidateReportDownloadView
)

app_name = 'interviewpanel'

urlpatterns = [
    path('create/', InterviewPanelView.as_view(), name='create_interview_panel'),
    path('get/', InterviewPanelView.as_view(), name='get_interview_panels'),
    path('get/<str:interview_panel_uuid>/', InterviewPanelView.as_view(), name='get_interview_panel'),
    path('update/<str:interview_panel_uuid>/', InterviewPanelView.as_view(), name='update_interview_panel'),
    path('delete/<str:interview_panel_uuid>/', InterviewPanelView.as_view(), name='delete_interview_panel'),

    # active panel
    path('start/<str:token>/', StartInterviewPanelView.as_view(), name='start_interview_panel'),

    # recruiter/admin candidate report APIs
    path('candidate/report/<str:session_uuid>/', CandidateReportDetailView.as_view(), name='candidate_report_detail'),
    path('candidate/report/<str:session_uuid>/download/', CandidateReportDownloadView.as_view(), name='candidate_report_download'),
]