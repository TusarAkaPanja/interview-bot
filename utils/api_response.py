from rest_framework import status
from rest_framework.response import Response
from typing import TypedDict, Optional

class ApiResponse(TypedDict):
    message: str
    data: Optional[dict]
    errors: Optional[str]
    status: str

class ApiResponseBuilder:
    @staticmethod
    def success(message: str, data: Optional[dict] = None, status_code: int = status.HTTP_200_OK) -> Response:
        response_data: ApiResponse = {
            'message': message,
            'status': 'success',
            'data': data
        }
        if data:
            response_data['data'] = data
        return Response(response_data, status=status_code)
    @staticmethod
    def error(message: str, errors: Optional[str] = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        response_data: ApiResponse = {
            'message': message,
            'status': 'error',
            'errors': errors
        }
        if errors:
            response_data['errors'] = errors
        return Response(response_data, status=status_code)
