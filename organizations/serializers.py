from rest_framework import serializers
from .models import Organization
from authentication.models import User, Role
from utils.crypto_utils import PasswordCrypto


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'uuid', 'name', 'address', 'email', 'created_at']
        read_only_fields = ['id', 'uuid', 'created_at']


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['name', 'address', 'email']

    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create organization
        organization = Organization.objects.create(
            name=validated_data['name'],
            address=validated_data['address'],
            email=validated_data['email'],
            created_by=user
        )
        user.organization = organization
        user.save()
        return organization


class AddHrSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    def validate_organization(self, value):
        if not value:
            raise serializers.ValidationError("Organization is required.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def create(self, validated_data):
        admin_user = self.context['request'].user
        organization = admin_user.organization
        
        if not organization:
            raise serializers.ValidationError("Admin user must belong to an organization.")
        try:
            hr_role = Role.objects.get(name__iexact='hr')
        except Role.DoesNotExist:
            raise serializers.ValidationError("HR role does not exist. Please run create_roles command.")

        # Generate random password if not provided manually by admin
        password = validated_data.get('password')
        if not password:
            password = PasswordCrypto.generate_random_password()

        salt = PasswordCrypto.generate_salt()
        hashed_password = PasswordCrypto.hash_password(password, salt)
        hr_user = User.objects.create_user(
            email=validated_data['email'],
            password=hashed_password,
            salt=salt,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role=hr_role,
            organization=organization
        )
        
        return hr_user

