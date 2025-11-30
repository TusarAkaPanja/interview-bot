from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from utils.api_response import ApiResponseBuilder
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    UserSerializer,
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    CandidateRegistrationSerializer
)

import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            return ApiResponseBuilder.success('User logged in successfully', serializer.validated_data)
        except Exception as e:
            logger.error(f'Error logging in user: {e}')
            if hasattr(e, 'detail'):
                return ApiResponseBuilder.error('Invalid credentials', str(e.detail))
            return ApiResponseBuilder.error('Error logging in user', str(e))

@method_decorator(csrf_exempt, name='dispatch')
class TokenRefreshView(BaseTokenRefreshView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == 200:
                return ApiResponseBuilder.success('Token refreshed successfully', {
                    'access': response.data['access']
                })
            return ApiResponseBuilder.error('Token refresh failed', response.data)
        except Exception as e:
            logger.error(f'Error refreshing token: {e}')
            return ApiResponseBuilder.error('Error refreshing token', str(e))

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return ApiResponseBuilder.success(
                'User registered successfully',
                UserSerializer(user).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('User registration failed', serializer.errors)

@method_decorator(csrf_exempt, name='dispatch')
class RegisterCandidateView(APIView):
    serializer_class = CandidateRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.organization:
            return ApiResponseBuilder.error(
                'User must belong to an organization to register candidates',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is admin or HR
        if not request.user.role:
            return ApiResponseBuilder.error(
                'User must have a role to register candidates',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        role_name = request.user.role.name.lower()
        if role_name not in ['admin', 'hr']:
            return ApiResponseBuilder.error(
                'Only admin or HR can register candidates',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            candidate = serializer.save()
            # Return candidate data (without password)
            candidate_data = {
                'id': candidate.id,
                'uuid': str(candidate.uuid),
                'email': candidate.email,
                'first_name': candidate.first_name,
                'last_name': candidate.last_name,
                'created_at': candidate.created_at
            }
            return ApiResponseBuilder.success(
                'Candidate registered successfully',
                candidate_data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Candidate registration failed', serializer.errors)