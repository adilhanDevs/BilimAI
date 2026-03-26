from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings

from apps.subscription.models import Subscription
from apps.subscription.services.subscription_service import SubscriptionService
from apps.users.models import User


@override_settings(HF_API_TOKEN=None)
class AiSessionsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            nickname="aiuser",
            email="aiuser@example.com",
            password="Str0ngP@ssw0rd",
        )
        SubscriptionService.create_subscription(self.user, Subscription.PlanType.MONTHLY)
        token_res = self.client.post(
            reverse("auth-login"),
            {"nickname": "aiuser", "password": "Str0ngP@ssw0rd"},
            format="json",
        )
        self.access = token_res.json()["data"]["access"]

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.access}"}

    def test_history_is_per_session(self):
        s1 = self.client.post(reverse("ai-sessions"), {"title": "S1"}, format="json", **self._auth()).json()["data"]
        s2 = self.client.post(reverse("ai-sessions"), {"title": "S2"}, format="json", **self._auth()).json()["data"]

        self.client.post(
            reverse("ai-chat"),
            {"message": "hello 1", "session_id": s1["id"]},
            format="json",
            **self._auth(),
        )
        self.client.post(
            reverse("ai-chat"),
            {"message": "hello 2", "session_id": s2["id"]},
            format="json",
            **self._auth(),
        )

        h1 = self.client.get(reverse("ai-history"), {"session_id": s1["id"]}, **self._auth())
        self.assertEqual(h1.status_code, status.HTTP_200_OK)
        results1 = h1.json()["data"]["results"]
        self.assertEqual(len(results1), 1)
        self.assertEqual(results1[0]["session_id"], s1["id"])
        self.assertEqual(results1[0]["message"], "hello 1")

        h2_default = self.client.get(reverse("ai-history"), **self._auth())
        results2 = h2_default.json()["data"]["results"]
        self.assertEqual(len(results2), 1)
        self.assertEqual(results2[0]["session_id"], s2["id"])
        self.assertEqual(results2[0]["message"], "hello 2")

        hall = self.client.get(reverse("ai-history"), {"all": "true"}, **self._auth())
        results_all = hall.json()["data"]["results"]
        self.assertEqual({row["message"] for row in results_all}, {"hello 1", "hello 2"})

