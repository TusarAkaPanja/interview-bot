from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission class to check if user is an admin of an organization
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not request.user.organization:
            return False
        
        # Check if user has admin role
        return request.user.role and request.user.role.name.lower() == 'admin'


class IsHr(permissions.BasePermission):
    """
    Permission class to check if user is HR of an organization
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not request.user.organization:
            return False
        
        # Check if user has HR role
        return request.user.role and request.user.role.name.lower() == 'hr'


class IsAdminOrHr(permissions.BasePermission):
    """
    Permission class to check if user is admin or HR of an organization
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not request.user.organization:
            return False
        
        # Check if user has admin or HR role
        if request.user.role:
            role_name = request.user.role.name.lower()
            return role_name in ['admin', 'hr']
        return False

