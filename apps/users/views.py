from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from common.responses import api_response

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .services.user_service import UserService


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.create_user(
            nickname=serializer.validated_data["nickname"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data.get("first_name") or "",
            last_name=serializer.validated_data.get("last_name") or "",
        )
        payload = UserSerializer(user).data
        return api_response(data=payload, status_code=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = UserService.authenticate_user(
            nickname=serializer.validated_data["nickname"],
            password=serializer.validated_data["password"],
        )
        return api_response(data=tokens)


class MeView(APIView):
    def get(self, request, *args, **kwargs):
        return api_response(data=UserSerializer(request.user).data)


class BilimTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return api_response(
                success=False,
                data=None,
                error=response.data,
                status_code=response.status_code,
            )
        return api_response(data=response.data)
