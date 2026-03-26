from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


class TokenRotationTests(APITestCase):
    def setUp(self):
        User.objects.create_user(
            nickname="rot",
            email="rot@example.com",
            password="Str0ngP@ssw0rd",
        )
        tokens = self.client.post(
            reverse("auth-login"),
            {"nickname": "rot", "password": "Str0ngP@ssw0rd"},
            format="json",
        ).json()["data"]
        self.refresh1 = tokens["refresh"]

    def test_refresh_rotates_and_blacklists_old_refresh(self):
        r1 = self.client.post(reverse("token-refresh"), {"refresh": self.refresh1}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        data = r1.json()["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        refresh2 = data["refresh"]
        self.assertNotEqual(refresh2, self.refresh1)

        old_again = self.client.post(reverse("token-refresh"), {"refresh": self.refresh1}, format="json")
        self.assertEqual(old_again.status_code, status.HTTP_401_UNAUTHORIZED)

