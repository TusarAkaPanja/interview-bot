from rest_framework import serializers
from .models import InterviewPanel, InterviewPanelQuestionDistribution, InterviewPanelQuestion, InterviewPanelCandidate, InterviewSession, InterviewAnswer, InterviewReportAnswerwiseFeedback
from questionbank.models import Category, Topic, Subtopic, Question
from authentication.models import Candidate

class QuestionDistributionSerializer(serializers.Serializer):
    topic_uuid = serializers.UUIDField()
    subtopic_uuid = serializers.UUIDField()
    easy = serializers.IntegerField(min_value=0, default=0)
    medium = serializers.IntegerField(min_value=0, default=0)
    hard = serializers.IntegerField(min_value=0, default=0)

    def validate(self, data):
        if data['easy'] + data['medium'] + data['hard'] == 0:
            raise serializers.ValidationError("At least one question count must be greater than 0")
        return data

class InterviewPanelCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    total_number_of_questions = serializers.IntegerField(min_value=1)
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    category_uuid = serializers.UUIDField()
    question_distributions = QuestionDistributionSerializer(many=True)
    candidate_uuids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)

    def validate(self, data):
        if data['start_datetime'] >= data['end_datetime']:
            raise serializers.ValidationError("end_datetime must be after start_datetime")
        
        total_distributed = sum(
            dist['easy'] + dist['medium'] + dist['hard']
            for dist in data['question_distributions']
        )
        
        if total_distributed != data['total_number_of_questions']:
            raise serializers.ValidationError(
                f"Total questions in distributions ({total_distributed}) must match total_number_of_questions ({data['total_number_of_questions']})"
            )
        
        return data

    def validate_category_uuid(self, value):
        try:
            Category.objects.get(uuid=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category not found")
        return value

    def validate_question_distributions(self, value):
        category_uuid = self.initial_data.get('category_uuid')
        if not category_uuid:
            raise serializers.ValidationError("category_uuid is required")
        
        try:
            category = Category.objects.get(uuid=category_uuid)
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category not found")
        
        topic_uuids = set()
        subtopic_uuids = set()
        
        for dist in value:
            topic_uuid = dist.get('topic_uuid')
            subtopic_uuid = dist.get('subtopic_uuid')
            
            try:
                topic = Topic.objects.get(uuid=topic_uuid, category=category)
            except Topic.DoesNotExist:
                raise serializers.ValidationError(f"Topic {topic_uuid} not found in category {category.name}")
            
            try:
                subtopic = Subtopic.objects.get(uuid=subtopic_uuid, topic=topic)
            except Subtopic.DoesNotExist:
                raise serializers.ValidationError(f"Subtopic {subtopic_uuid} not found in topic {topic.name}")
            
            topic_uuids.add(topic_uuid)
            subtopic_uuids.add(subtopic_uuid)
        
        return value

    def validate_candidate_uuids(self, value):
        if not value:
            return value
        
        organization = self.context.get('organization')
        if not organization:
            return value
        
        for candidate_uuid in value:
            try:
                candidate = Candidate.objects.get(uuid=candidate_uuid, organization=organization)
            except Candidate.DoesNotExist:
                raise serializers.ValidationError(f"Candidate {candidate_uuid} not found in organization")
        
        return value

class InterviewPanelUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewPanel
        fields = ['name', 'description', 'start_datetime', 'end_datetime']

class InterviewPanelSerializer(serializers.ModelSerializer):
    question_distributions = serializers.SerializerMethodField()
    candidates = serializers.SerializerMethodField()
    
    class Meta:
        model = InterviewPanel
        fields = [
            'uuid', 'name', 'description', 'total_number_of_questions',
            'start_datetime', 'end_datetime', 'is_active', 'organization',
            'created_at', 'updated_at', 'question_distributions', 'candidates'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at', 'organization']

    def get_question_distributions(self, obj):
        distributions = obj.interview_panel_question_distributions.filter(is_deleted=False)
        return [{
            'uuid': dist.uuid,
            'category': dist.category.name,
            'topic': dist.topic.name,
            'subtopic': dist.subtopic.name,
            'easy': dist.number_of_easy_questions,
            'medium': dist.number_of_medium_questions,
            'hard': dist.number_of_hard_questions,
            'total': dist.number_of_questions
        } for dist in distributions]

    def get_candidates(self, obj):
        candidates = obj.interview_panel_candidates.filter(is_deleted=False)
        candidates_data = []
        for cand in candidates:
            try:
                session = InterviewSession.objects.get(
                    interview_panel_candidate=cand,
                    is_deleted=False
                )
                status = session.status
                started_at = session.started_at
                completed_at = session.completed_at
                cumulative_score = session.cumulative_score
                has_report = session.status == 'completed' and bool(session.report_pdf_path)
                session_uuid = str(session.uuid)
            except InterviewSession.DoesNotExist:
                status = 'pending'
                started_at = None
                completed_at = None
                cumulative_score = None
                has_report = False
                session_uuid = None
            
            candidates_data.append({
                'uuid': cand.uuid,
                'candidate_uuid': cand.candidate.uuid,
                'candidate_name': f"{cand.candidate.first_name} {cand.candidate.last_name}",
                'candidate_email': cand.candidate.email,
                'token': cand.token,
                'token_expires_at': cand.token_expires_at,
                'score': cand.score,
                'session_uuid': session_uuid,
                'status': status,
                'started_at': started_at,
                'completed_at': completed_at,
                'cumulative_score': cumulative_score,
                'has_report': has_report
            })
        return candidates_data

class CandidateInterviewSessionSerializer(serializers.Serializer):
    """Serializer for listing interview sessions for a candidate"""
    session_uuid = serializers.UUIDField()
    interview_panel_name = serializers.CharField()
    interview_panel_uuid = serializers.UUIDField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    cumulative_score = serializers.FloatField(allow_null=True)
    has_report = serializers.BooleanField()
    report_pdf_path = serializers.CharField(allow_null=True)

class CandidateReportDetailSerializer(serializers.Serializer):
    """Serializer for detailed report data for UI display"""
    session_uuid = serializers.UUIDField()
    candidate_name = serializers.CharField()
    candidate_email = serializers.EmailField()
    interview_panel_name = serializers.CharField()
    interview_panel_description = serializers.CharField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    cumulative_score = serializers.FloatField(allow_null=True)
    technical_competency_score = serializers.FloatField()
    behavioral_competency_score = serializers.FloatField()
    psychological_competency_score = serializers.FloatField()
    answers = serializers.ListField()

