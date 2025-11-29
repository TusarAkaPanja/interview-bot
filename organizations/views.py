from rest_framework import status, permissions
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from utils.api_response import ApiResponseBuilder
from .models import Organization
from .serializers import (
    OrganizationSerializer,
    OrganizationCreateSerializer,
    AddHrSerializer
)
from authentication.serializers import UserSerializer

import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class CreateOrganizationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationCreateSerializer

    def post(self, request):
        if request.user.organization:
            return ApiResponseBuilder.error(
                'User already belongs to an organization',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            organization = serializer.save()
            from authentication.models import Role
            try:
                admin_role = Role.objects.get(name__iexact='admin')
                request.user.role = admin_role
                request.user.save()
            except Role.DoesNotExist:
                logger.warning("Admin role does not exist")
            return ApiResponseBuilder.success(
                'Organization created successfully',
                OrganizationSerializer(organization).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Organization creation failed', serializer.errors)


@method_decorator(csrf_exempt, name='dispatch')
class AddHrView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddHrSerializer

    def post(self, request):
        if not request.user.organization:
            return ApiResponseBuilder.error(
                'User must belong to an organization',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.role or request.user.role.name.lower() != 'admin':
            return ApiResponseBuilder.error(
                'Only organization admin can add HR users',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            hr_user = serializer.save()
            return ApiResponseBuilder.success(
                'HR user added successfully',
                UserSerializer(hr_user).data,
                status_code=status.HTTP_201_CREATED
            )
        return ApiResponseBuilder.error('Failed to add HR user', serializer.errors)
