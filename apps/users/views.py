from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiExample
from common.serializers import ApiResponseSerializer

from common.responses import api_response

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .services.user_service import UserService


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: ApiResponseSerializer},
        examples=[
            OpenApiExample(
                'Register example',
                value={
                    'nickname': 'johndoe',
                    'email': 'john@example.com',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'password': 'strongpassword',
                    'password2': 'strongpassword',
                },
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.create_user(
            nickname=serializer.validated_data["nickname"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data.get("first_name") or "",
            last_name=serializer.validated_data.get("last_name") or "",
            native_language=serializer.validated_data.get("native_language") or "ky",
            target_language=serializer.validated_data.get("target_language") or "tr",
        )
        payload = UserSerializer(user).data
        return api_response(data=payload, status_code=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: ApiResponseSerializer},
        examples=[
            OpenApiExample(
                'Login example',
                value={'nickname': 'johndoe', 'password': 'strongpassword'},
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = UserService.authenticate_user(
            nickname=serializer.validated_data["nickname"],
            password=serializer.validated_data["password"],
        )
        return api_response(data=tokens)


class MeView(APIView):
    @extend_schema(responses=ApiResponseSerializer)
    def get(self, request, *args, **kwargs):
        return api_response(data=UserSerializer(request.user).data)

    @extend_schema(request=UserSerializer, responses=ApiResponseSerializer)
    def patch(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(data=serializer.data)


class BilimTokenRefreshView(TokenRefreshView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: ApiResponseSerializer, 401: ApiResponseSerializer})
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
