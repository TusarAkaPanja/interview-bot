from django.db import models
import uuid
from organizations.models import Organization
from authentication.models import User

# Create your models here.

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_categories')
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_categories')

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        db_table = 'categories'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_category_name')
        ]

    def __str__(self):
        return self.name
    
    def save(self, request=None, *args, **kwargs):
        if request and not self.created_by:
            self.created_by = request.user
        if request and not self.updated_by:
            self.updated_by = request.user
        super().save(*args, **kwargs)
        
class Topic(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='topics')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_topics', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_topics', null=True, blank=True)

    class Meta:
        verbose_name = 'Topic'
        verbose_name_plural = 'Topics'
        db_table = 'topics'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['name', 'category'], name='unique_topic_name_per_category')
        ]

    def __str__(self):
        return self.name
    
    def save(self, request=None, *args, **kwargs):
        if request and not self.created_by:
            self.created_by = request.user
        if request and not self.updated_by:
            self.updated_by = request.user
        super().save(*args, **kwargs)
        
class Subtopic(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_subtopics', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_subtopics', null=True, blank=True)

    class Meta:
        verbose_name = 'Subtopic'
        verbose_name_plural = 'Subtopics'
        db_table = 'subtopics'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['name', 'topic'], name='unique_subtopic_name_per_topic')
        ]

    def __str__(self):
        return self.name
    
    def save(self, request=None, *args, **kwargs):
        if request and not self.created_by:
            self.created_by = request.user
        if request and not self.updated_by:
            self.updated_by = request.user
        super().save(*args, **kwargs)


class DifficultyLevel(models.TextChoices):
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'

class Question(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='questions')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)

    # adaptive analysis parameters
    question = models.TextField()
    difficulty_level = models.CharField(max_length=255, choices=DifficultyLevel.choices, default=DifficultyLevel.EASY)
    expected_answer = models.TextField()
    expected_time_in_seconds = models.IntegerField(default=60)
    ideal_answer_summary = models.TextField(blank=True, null=True)
    red_flags = models.JSONField(default=list)

    expected_keywords = models.JSONField(default=list)
    expected_keywords_coverage = models.FloatField(default=0.1)

    score_weight_technical = models.FloatField(default=0.5)
    score_weight_domain_knowledge = models.FloatField(default=0.3)
    score_weight_communication = models.FloatField(default=0.1)
    score_weight_problem_solving = models.FloatField(default=0.05)
    score_weight_creativity = models.FloatField(default=0.05)
    score_weight_attention_to_detail = models.FloatField(default=0.05)
    score_weight_time_management = models.FloatField(default=0.05)
    score_weight_stress_management = models.FloatField(default=0.05)
    score_weight_adaptability = models.FloatField(default=0.05)
    score_weight_confidence = models.FloatField(default=0.05)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_questions', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_questions', null=True, blank=True)

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        db_table = 'questions'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Questions are shared across organizations, no organization field needed
        super().save(*args, **kwargs)


class QuestionConfigurationStatus(models.TextChoices):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
   

class QuestionConfiguration(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='question_configurations')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='question_configurations')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='question_configurations')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='question_configurations', null=True, blank=True)
    status = models.CharField(max_length=255, choices=QuestionConfigurationStatus.choices, default=QuestionConfigurationStatus.PENDING)
    number_of_questions_to_generate = models.IntegerField(default=0)
    number_of_questions_failed = models.IntegerField(default=0)
    number_of_questions_completed = models.IntegerField(default=0)
    number_of_questions_pending = models.IntegerField(default=0)
    number_of_questions_in_progress = models.IntegerField(default=0)
    time_taken_in_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_question_configurations', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_question_configurations', null=True, blank=True)

    class Meta:
        verbose_name = 'Question Configuration'
        verbose_name_plural = 'Question Configurations'
        db_table = 'question_configurations'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, request=None, *args, **kwargs):
        if request:
            if not self.created_by:
                self.created_by = request.user
            if not self.updated_by:
                self.updated_by = request.user
            if not self.organization:
                self.organization = request.user.organization
        super().save(*args, **kwargs)