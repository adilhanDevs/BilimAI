from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.subscription.models import Subscription
from apps.subscription.services.subscription_service import SubscriptionService
from apps.users.models import User


class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            nickname="subuser",
            email="subuser@example.com",
            password="testpass123",
        )

    def test_create_subscription(self):
        sub = SubscriptionService.create_subscription(self.user, Subscription.PlanType.MONTHLY)
        self.assertTrue(sub.is_active)
        self.assertEqual(sub.plan_type, Subscription.PlanType.MONTHLY)

    def test_expires_after_30_days(self):
        past = timezone.now() - timedelta(days=31)
        sub = Subscription.objects.create(
            user=self.user,
            plan_type=Subscription.PlanType.MONTHLY,
            is_active=True,
            last_payment_date=past,
        )
        SubscriptionService.sync_subscription_flags(sub)
        sub.refresh_from_db()
        self.assertFalse(sub.is_active)

    def test_user_has_active_subscription_false_without_row(self):
        self.assertFalse(SubscriptionService.user_has_active_subscription(self.user))
