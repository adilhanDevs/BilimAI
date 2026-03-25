from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed

from apps.users.models import User
from apps.users.services.user_service import UserService


class UserServiceTests(TestCase):
    def test_create_and_authenticate(self):
        UserService.create_user(
            nickname="svc",
            email="svc@example.com",
            password="Testpass123!",
        )
        tokens = UserService.authenticate_user("svc", "Testpass123!")
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)

    def test_authenticate_invalid(self):
        User.objects.create_user(
            nickname="svc2",
            email="svc2@example.com",
            password="Testpass123!",
        )
        with self.assertRaises(AuthenticationFailed):
            UserService.authenticate_user("svc2", "wrong")
