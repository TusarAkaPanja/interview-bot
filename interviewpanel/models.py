from django.db import models
from organizations.models import Organization
from authentication.models import User, Candidate
from questionbank.models import Category, Topic, Subtopic, Question
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import uuid
import random
import string

class InterviewPanel(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    total_number_of_questions = models.IntegerField(default=0)
    
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='interview_panels')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_interview_panels', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_interview_panels', null=True, blank=True)

    class Meta:
        verbose_name = 'Interview Panel'
        verbose_name_plural = 'Interview Panels'
        db_table = 'interview_panels'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def check_and_deactivate(self):
        if self.end_datetime < timezone.now() and self.is_active:
            self.is_active = False
            self.save(update_fields=['is_active'])

@receiver(pre_save, sender=InterviewPanel)
def check_panel_expiry(sender, instance, **kwargs):
    if instance.end_datetime < timezone.now():
        instance.is_active = False

# category / topic / subtopic wise questions distribution
class InterviewPanelQuestionDistribution(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    interview_panel = models.ForeignKey(InterviewPanel, on_delete=models.CASCADE, related_name='interview_panel_question_distributions')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='interview_panel_question_distributions')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='interview_panel_question_distributions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='interview_panel_question_distributions')
    number_of_questions = models.IntegerField(default=0)
    number_of_hard_questions = models.IntegerField(default=0)
    number_of_medium_questions = models.IntegerField(default=0)
    number_of_easy_questions = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_interview_panel_question_distributions', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_interview_panel_question_distributions', null=True, blank=True)

    class Meta:
        verbose_name = 'Interview Panel Question Distribution'
        verbose_name_plural = 'Interview Panel Question Distributions'
        db_table = 'interview_panel_question_distributions'
        ordering = ['-created_at']

    def __str__(self):
        return self.category.name + ' - ' + self.topic.name + ' - ' + self.subtopic.name

# interview panel question
class InterviewPanelQuestion(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    interview_panel = models.ForeignKey(InterviewPanel, on_delete=models.CASCADE, related_name='interview_panel_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='interview_panel_questions')
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_interview_panel_questions', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_interview_panel_questions', null=True, blank=True)

    class Meta:
        verbose_name = 'Interview Panel Question'
        verbose_name_plural = 'Interview Panel Questions'
        db_table = 'interview_panel_questions'
        ordering = ['-created_at']

    def __str__(self):
        return self.question.name

class InterviewPanelCandidate(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    interview_panel = models.ForeignKey(InterviewPanel, on_delete=models.CASCADE, related_name='interview_panel_candidates')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='interview_panel_candidates')
    token = models.CharField(max_length=255, null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    total_time_taken_in_seconds = models.IntegerField(default=0)
    number_of_questions_answered = models.IntegerField(default=0)
    number_of_questions_not_answered = models.IntegerField(default=0)
    number_of_questions_skipped = models.IntegerField(default=0)
    number_of_questions_not_attempted = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Interview Panel Candidate'
        verbose_name_plural = 'Interview Panel Candidates'
        db_table = 'interview_panel_candidates'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.candidate.first_name} {self.candidate.last_name}"

    def generate_token(self):
        self.token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.token_expires_at = self.interview_panel.end_datetime
        self.save()
        return self.token
        