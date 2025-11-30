from rest_framework import serializers
from .models import Category, Topic, Subtopic, Question, QuestionConfiguration, DifficultyLevel
from organizations.models import Organization
from authentication.models import User


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'uuid', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        if self.instance is None:
            if Category.objects.filter(name__iexact=value).exists():
                raise serializers.ValidationError("A category with this name already exists.")
        else:
            if Category.objects.filter(name__iexact=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("A category with this name already exists.")
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        try:
            category = Category.objects.create(
                name=validated_data['name'],
                description=validated_data.get('description', ''),
                created_by=user,
                updated_by=user
            )
        except Exception as e:
            if 'unique_category_name' in str(e):
                raise serializers.ValidationError({"name": "A category with this name already exists."})
            raise
        return category
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if user:
            instance.updated_by = user
        instance.save()
        return instance


class TopicSerializer(serializers.ModelSerializer):
    category_uuid = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Topic
        fields = ['id', 'uuid', 'name', 'description', 'category', 'category_uuid', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uuid', 'category', 'created_at', 'updated_at']
    
    def validate(self, data):
        if self.instance is None and 'category_uuid' not in data:
            raise serializers.ValidationError({"category_uuid": "This field is required."})
        return data
    
    def validate_name(self, value):
        category_uuid = self.initial_data.get('category_uuid')
        if category_uuid:
            try:
                category = Category.objects.get(uuid=category_uuid)
                if self.instance is None:
                    if Topic.objects.filter(name__iexact=value, category=category).exists():
                        raise serializers.ValidationError("A topic with this name already exists in this category.")
                else:
                    if Topic.objects.filter(name__iexact=value, category=category).exclude(pk=self.instance.pk).exists():
                        raise serializers.ValidationError("A topic with this name already exists in this category.")
            except Category.DoesNotExist:
                pass
        return value
    
    def validate_category_uuid(self, value):
        try:
            Category.objects.get(uuid=value)
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category not found.")
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        category_uuid = validated_data.pop('category_uuid')
        category = Category.objects.get(uuid=category_uuid)
        
        try:
            topic = Topic.objects.create(
                name=validated_data['name'],
                description=validated_data.get('description', ''),
                category=category,
                created_by=user,
                updated_by=user
            )
        except Exception as e:
            if 'unique_topic_name_per_category' in str(e):
                raise serializers.ValidationError({"name": "A topic with this name already exists in this category."})
            raise
        return topic
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        category_uuid = validated_data.pop('category_uuid', None)
        
        if category_uuid:
            instance.category = Category.objects.get(uuid=category_uuid)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if user:
            instance.updated_by = user
        instance.save()
        return instance


class SubtopicSerializer(serializers.ModelSerializer):
    topic_uuid = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Subtopic
        fields = ['id', 'uuid', 'name', 'description', 'topic', 'topic_uuid', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uuid', 'topic', 'created_at', 'updated_at']
    
    def validate(self, data):
        if self.instance is None and 'topic_uuid' not in data:
            raise serializers.ValidationError({"topic_uuid": "This field is required."})
        return data
    
    def validate_name(self, value):
        topic_uuid = self.initial_data.get('topic_uuid')
        if topic_uuid:
            try:
                topic = Topic.objects.get(uuid=topic_uuid)
                if self.instance is None:
                    if Subtopic.objects.filter(name__iexact=value, topic=topic).exists():
                        raise serializers.ValidationError("A subtopic with this name already exists in this topic.")
                else:
                    if Subtopic.objects.filter(name__iexact=value, topic=topic).exclude(pk=self.instance.pk).exists():
                        raise serializers.ValidationError("A subtopic with this name already exists in this topic.")
            except Topic.DoesNotExist:
                pass
        return value
    
    def validate_topic_uuid(self, value):
        try:
            Topic.objects.get(uuid=value)
            return value
        except Topic.DoesNotExist:
            raise serializers.ValidationError("Topic not found.")
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        topic_uuid = validated_data.pop('topic_uuid')
        topic = Topic.objects.get(uuid=topic_uuid)
        
        try:
            subtopic = Subtopic.objects.create(
                name=validated_data['name'],
                description=validated_data.get('description', ''),
                topic=topic,
                created_by=user,
                updated_by=user
            )
        except Exception as e:
            if 'unique_subtopic_name_per_topic' in str(e):
                raise serializers.ValidationError({"name": "A subtopic with this name already exists in this topic."})
            raise
        return subtopic
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        topic_uuid = validated_data.pop('topic_uuid', None)
        
        if topic_uuid:
            instance.topic = Topic.objects.get(uuid=topic_uuid)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if user:
            instance.updated_by = user
        instance.save()
        return instance


class QuestionSerializer(serializers.ModelSerializer):
    category_uuid = serializers.UUIDField(write_only=True, required=False)
    topic_uuid = serializers.UUIDField(write_only=True, required=False)
    subtopic_uuid = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'uuid', 'name', 'description', 'category', 'topic', 'subtopic',
            'category_uuid', 'topic_uuid', 'subtopic_uuid',
            'question', 'difficulty_level', 'expected_answer', 'expected_time_in_seconds',
            'ideal_answer_summary', 'red_flags', 'embedding', 'expected_keywords',
            'expected_keywords_coverage', 'score_weight_technical', 'score_weight_domain_knowledge',
            'score_weight_communication', 'score_weight_problem_solving', 'score_weight_creativity',
            'score_weight_attention_to_detail', 'score_weight_time_management',
            'score_weight_stress_management', 'score_weight_adaptability', 'score_weight_confidence',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'category', 'topic', 'subtopic', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        category_uuid = validated_data.pop('category_uuid', None)
        topic_uuid = validated_data.pop('topic_uuid', None)
        subtopic_uuid = validated_data.pop('subtopic_uuid', None)
        
        if category_uuid:
            category = Category.objects.get(uuid=category_uuid)
        else:
            category = validated_data.get('category')
        
        if topic_uuid:
            topic = Topic.objects.get(uuid=topic_uuid)
        else:
            topic = validated_data.get('topic')
        
        subtopic = None
        if subtopic_uuid:
            subtopic = Subtopic.objects.get(uuid=subtopic_uuid)
        elif 'subtopic' in validated_data:
            subtopic = validated_data.get('subtopic')
        
        question = Question.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            category=category,
            topic=topic,
            subtopic=subtopic,
            question=validated_data['question'],
            difficulty_level=validated_data.get('difficulty_level', 'easy'),
            expected_answer=validated_data['expected_answer'],
            expected_time_in_seconds=validated_data.get('expected_time_in_seconds', 60),
            ideal_answer_summary=validated_data.get('ideal_answer_summary', ''),
            red_flags=validated_data.get('red_flags', []),
            embedding=validated_data.get('embedding', {}),
            expected_keywords=validated_data.get('expected_keywords', []),
            expected_keywords_coverage=validated_data.get('expected_keywords_coverage', 0.1),
            score_weight_technical=round(validated_data.get('score_weight_technical', 0.5), 2),
            score_weight_domain_knowledge=round(validated_data.get('score_weight_domain_knowledge', 0.3), 2),
            score_weight_communication=round(validated_data.get('score_weight_communication', 0.1), 2),
            score_weight_problem_solving=round(validated_data.get('score_weight_problem_solving', 0.05), 2),
            score_weight_creativity=round(validated_data.get('score_weight_creativity', 0.05), 2),
            score_weight_attention_to_detail=round(validated_data.get('score_weight_attention_to_detail', 0.05), 2),
            score_weight_time_management=round(validated_data.get('score_weight_time_management', 0.05), 2),
            score_weight_stress_management=round(validated_data.get('score_weight_stress_management', 0.05), 2),
            score_weight_adaptability=round(validated_data.get('score_weight_adaptability', 0.05), 2),
            score_weight_confidence=round(validated_data.get('score_weight_confidence', 0.05), 2),
            created_by=user,
            updated_by=user
        )
        return question
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        category_uuid = validated_data.pop('category_uuid', None)
        topic_uuid = validated_data.pop('topic_uuid', None)
        subtopic_uuid = validated_data.pop('subtopic_uuid', None)
        
        if category_uuid:
            instance.category = Category.objects.get(uuid=category_uuid)
        if topic_uuid:
            instance.topic = Topic.objects.get(uuid=topic_uuid)
        if subtopic_uuid is not None:
            if subtopic_uuid:
                instance.subtopic = Subtopic.objects.get(uuid=subtopic_uuid)
            else:
                instance.subtopic = None
        
        score_weight_fields = [
            'score_weight_technical', 'score_weight_domain_knowledge', 'score_weight_communication',
            'score_weight_problem_solving', 'score_weight_creativity', 'score_weight_attention_to_detail',
            'score_weight_time_management', 'score_weight_stress_management',
            'score_weight_adaptability', 'score_weight_confidence'
        ]
        
        for attr, value in validated_data.items():
            if attr in score_weight_fields and isinstance(value, (int, float)):
                value = round(float(value), 2)
            setattr(instance, attr, value)
        if user:
            instance.updated_by = user
        instance.save()
        return instance


class DifficultyPartitionSerializer(serializers.Serializer):
    easy = serializers.FloatField(min_value=0, max_value=100)
    medium = serializers.FloatField(min_value=0, max_value=100)
    hard = serializers.FloatField(min_value=0, max_value=100)

    def validate(self, data):
        total = data.get('easy', 0) + data.get('medium', 0) + data.get('hard', 0)
        if abs(total - 100.0) > 0.01:
            raise serializers.ValidationError(
                "Difficulty partition percentages must sum to 100. "
                f"Current sum: {total}%"
            )
        return data


class QuestionGenerationRequestSerializer(serializers.Serializer):
    category_uuid = serializers.UUIDField(required=True)
    topic_uuid = serializers.UUIDField(required=True)
    subtopic_uuid = serializers.UUIDField(required=False, allow_null=True)
    number_of_questions = serializers.IntegerField(min_value=1, max_value=1000, required=True)
    difficulty_partitions = DifficultyPartitionSerializer(required=True)

    def validate_category_uuid(self, value):
        try:
            category = Category.objects.get(uuid=value)
            if category.created_by.organization != self.context['request'].user.organization:
                raise serializers.ValidationError("Category does not belong to your organization.")
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category not found.")

    def validate_topic_uuid(self, value):
        try:
            topic = Topic.objects.get(uuid=value)
            if topic.created_by and topic.created_by.organization != self.context['request'].user.organization:
                raise serializers.ValidationError("Topic does not belong to your organization.") 
            category_uuid = self.initial_data.get('category_uuid')
            if category_uuid:
                try:
                    category = Category.objects.get(uuid=category_uuid)
                    if topic.category != category:
                        raise serializers.ValidationError("Topic does not belong to the specified category.")
                except Category.DoesNotExist:
                    pass
            return value
        except Topic.DoesNotExist:
            raise serializers.ValidationError("Topic not found.")

    def validate_subtopic_uuid(self, value):
        if value is None:
            return value
        try:
            subtopic = Subtopic.objects.get(uuid=value)
            if subtopic.created_by and subtopic.created_by.organization != self.context['request'].user.organization:
                raise serializers.ValidationError("Subtopic does not belong to your organization.")
            topic_uuid = self.initial_data.get('topic_uuid')
            if topic_uuid:
                try:
                    topic = Topic.objects.get(uuid=topic_uuid)
                    if subtopic.topic != topic:
                        raise serializers.ValidationError("Subtopic does not belong to the specified topic.")
                except Topic.DoesNotExist:
                    pass
            return value
        except Subtopic.DoesNotExist:
            raise serializers.ValidationError("Subtopic not found.")


class QuestionConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionConfiguration
        fields = [
            'id', 'uuid', 'name', 'organization', 'category', 'topic', 'subtopic',
            'status', 'number_of_questions_to_generate',
            'number_of_questions_failed', 'number_of_questions_completed',
            'number_of_questions_pending', 'number_of_questions_in_progress',
            'time_taken_in_seconds', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'uuid', 'status', 'number_of_questions_failed',
            'number_of_questions_completed', 'number_of_questions_pending',
            'number_of_questions_in_progress', 'time_taken_in_seconds',
            'created_at', 'updated_at'
        ]

