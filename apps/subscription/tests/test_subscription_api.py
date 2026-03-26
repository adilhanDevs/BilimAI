from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.test import override_settings
from apps.subscription.models import Subscription, SubscriptionPlan
from .factories import UserFactory, SubscriptionPlanFactory, SubscriptionFactory

@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class SubscriptionAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(name="Test Plan", is_active=True)
        self.inactive_plan = SubscriptionPlanFactory(name="Inactive", is_active=False)
        
    def test_get_plans(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("subscription-plan-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming ApiResponseSerializer wrapping "data"
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["name"], "Test Plan")

    def test_create_subscription_api(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("subscription-list")
        response = self.client.post(url, {"plan_id": self.plan.id})
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sub_id = response.data["data"]["id"]
        sub = Subscription.objects.get(id=sub_id)
        
        self.assertEqual(sub.status, Subscription.Status.PENDING)
        self.assertEqual(sub.user, self.user)
        
    def test_get_me_subscription(self):
        # Create multiple subscriptions to ensure we get the latest / active
        sub1 = SubscriptionFactory(user=self.user, plan=self.plan, is_active=False, status=Subscription.Status.EXPIRED)
        import time
        time.sleep(0.1) # ensure creation order is preserved strictly
        sub2 = SubscriptionFactory(user=self.user, plan=self.plan, is_active=True, status=Subscription.Status.ACTIVE)
        
        self.client.force_authenticate(user=self.user)
        url = reverse("subscription-me")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], sub2.id)

    def test_unauthorized_access(self):
        url = reverse("subscription-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
