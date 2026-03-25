from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.subscription.models import Subscription
from apps.subscription.services.subscription_service import SubscriptionService
from apps.users.models import User


class AuthAPITests(APITestCase):
    def test_register_login_me(self):
        reg = self.client.post(
            reverse("auth-register"),
            {
                "nickname": "apiuser",
                "email": "apiuser@example.com",
                "password": "Str0ngP@ssw0rd",
                "password2": "Str0ngP@ssw0rd",
                "first_name": "Api",
                "last_name": "User",
            },
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.assertTrue(reg.json()["success"])

        token_res = self.client.post(
            reverse("auth-login"),
            {"nickname": "apiuser", "password": "Str0ngP@ssw0rd"},
            format="json",
        )
        self.assertEqual(token_res.status_code, status.HTTP_200_OK)
        access = token_res.json()["data"]["access"]

        me = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.json()["data"]["nickname"], "apiuser")


class ProtectedRouteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            nickname="pro",
            email="pro@example.com",
            password="Str0ngP@ssw0rd",
        )
        SubscriptionService.create_subscription(self.user, Subscription.PlanType.MONTHLY)
        token_res = self.client.post(
            reverse("auth-login"),
            {"nickname": "pro", "password": "Str0ngP@ssw0rd"},
            format="json",
        )
        self.access = token_res.json()["data"]["access"]

    def test_ai_chat_requires_subscription(self):
        User.objects.create_user(
            nickname="nosub",
            email="nosub@example.com",
            password="Str0ngP@ssw0rd",
        )
        tok = self.client.post(
            reverse("auth-login"),
            {"nickname": "nosub", "password": "Str0ngP@ssw0rd"},
            format="json",
        ).json()["data"]["access"]
        res = self.client.post(
            reverse("ai-chat"),
            {"message": "hi"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tok}",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        ok = self.client.post(
            reverse("ai-chat"),
            {"message": "hi"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ok.json()["success"])
