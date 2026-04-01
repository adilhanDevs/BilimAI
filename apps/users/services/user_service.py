import logging

from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def create_user(
        nickname: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        native_language: str = "ky",
        target_language: str = "tr",
    ) -> User:
        if not nickname or not email or not password:
            raise ValueError("Nickname, email, and password are required.")
        return User.objects.create_user(
            nickname=nickname,
            email=email,
            password=password,
            first_name=first_name or "",
            last_name=last_name or "",
            native_language=native_language or "ky",
            target_language=target_language or "tr",
        )

    @staticmethod
    def authenticate_user(nickname: str, password: str) -> dict:
        user = authenticate(request=None, username=nickname, password=password)
        if user is None:
            logger.info("Failed login attempt for nickname=%s", nickname)
            raise AuthenticationFailed("Invalid credentials.")
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}

    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        return User.objects.get(pk=user_id)
