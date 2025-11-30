from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
from .models import User, Role, Candidate


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'uuid', 'name']


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_uuid = serializers.UUIDField(source='role.uuid', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'uuid', 'email', 'role', 'role_uuid', 'is_active', 'created_at']
        read_only_fields = ['id', 'uuid', 'created_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name']
        read_only_fields = ['id', 'uuid', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        try:
            admin_role = Role.objects.get(name__iexact='admin')
        except Role.DoesNotExist:
            raise serializers.ValidationError({'role': 'Admin role does not exist. Please run create_roles command.'})
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=password,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role=admin_role
        )
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'
    
    def validate(self, attrs):
        email = attrs.get('email') or attrs.get(self.username_field)
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError('Must include "email" and "password".')
        
        from django.contrib.auth import authenticate
        user = authenticate(request=self.context.get('request'), username=email, password=password) 
        if not user:
            raise serializers.ValidationError('No active account found with the given credentials')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        self.user = user
        refresh = self.get_token(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
       
        token['user_uuid'] = str(user.uuid)
        if user.role:
            token['role'] = user.role.name
        else:
            token['role'] = None
            
        return token

class CandidateRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Candidate
        fields = ['email', 'first_name', 'last_name', 'password']
        read_only_fields = ['id', 'uuid', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        organization = user.organization
        
        if not organization:
            raise serializers.ValidationError('User must belong to an organization to register candidates')
        password = validated_data.pop('password', None)
        if not password:
            password = Candidate.generate_random_password()
        candidate = Candidate.objects.create(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            organization=organization
        )
        candidate.set_candidate_password(password)
        
        return candidate