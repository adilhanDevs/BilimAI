from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings
from django.utils import timezone

from apps.subscription.models import Subscription, SubscriptionPlan
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

    def test_patch_me(self):
        user = User.objects.create_user(
            nickname="patchme",
            email="patchme@example.com",
            password="Str0ngP@ssw0rd",
        )
        token_res = self.client.post(
            reverse("auth-login"),
            {"nickname": "patchme", "password": "Str0ngP@ssw0rd"},
            format="json",
        )
        access = token_res.json()["data"]["access"]

        res = self.client.patch(
            reverse("auth-me"),
            {
                "native_language": "en",
                "target_language": "ky",
                "daily_goal_xp": 50,
                "onboarding_completed": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        self.assertEqual(data["native_language"], "en")
        self.assertEqual(data["target_language"], "ky")
        self.assertEqual(data["daily_goal_xp"], 50)
        self.assertTrue(data["onboarding_completed"])

        user.refresh_from_db()
        self.assertEqual(user.native_language, "en")
        self.assertEqual(user.target_language, "ky")
        self.assertEqual(user.daily_goal_xp, 50)
        self.assertTrue(user.onboarding_completed)


@override_settings(HF_API_TOKEN=None)
class ProtectedRouteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            nickname="pro",
            email="pro@example.com",
            password="Str0ngP@ssw0rd",
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Monthly", code="monthly", duration_days=30, price=Decimal("100.00")
        )
        self.sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            is_active=True,
            starts_at=timezone.now(),
        )
        token_res = self.client.post(
            reverse("auth-login"),
            {"nickname": "pro", "password": "Str0ngP@ssw0rd"},
            format="json",
        )
        self.access = token_res.json()["data"]["access"]

    def test_ai_chat_limits(self):
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
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()["data"]
        self.assertEqual(data["limit"], 10)  # Default for free_auth
        self.assertEqual(data["used"], 1)
        self.assertEqual(data["remaining"], 9)

        # Pro user from setUp should have 100 limit
        ok = self.client.post(
            reverse("ai-chat"),
            {"message": "hi"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ok.json()["data"]["limit"], 100)
