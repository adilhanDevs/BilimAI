import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase

from apps.subscription.models import Subscription
from apps.subscription.services.subscription_service import SubscriptionService
from .factories import UserFactory, SubscriptionPlanFactory, SubscriptionFactory, SubscriptionPaymentFactory

class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(duration_days=30)

    # 1.1 Create Subscription
    def test_create_subscription(self):
        sub = SubscriptionService.create_subscription(self.user, self.plan)
        
        self.assertEqual(sub.status, Subscription.Status.PENDING)
        self.assertFalse(sub.is_active)
        self.assertEqual(sub.user, self.user)
        self.assertIsNotNone(sub.starts_at)
        self.assertEqual(sub.ends_at, sub.starts_at + timedelta(days=self.plan.duration_days))

    # 1.2 Activate Subscription via Payment
    def test_payment_activates_subscription(self):
        sub = SubscriptionService.create_subscription(self.user, self.plan)
        
        # Simulate successful payment via webhook processing
        payload = {
            "subscription_id": sub.id,
            "provider_payment_id": "txn_activate",
            "amount": str(self.plan.price),
            "currency": self.plan.currency,
            "succeeded": True,
            "provider": "mock"
        }
        SubscriptionService.process_webhook_payment(payload)
        
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertTrue(sub.is_active)
        self.assertIsNotNone(sub.last_payment_date)

    # 1.3 Renewal Logic
    def test_subscription_renewal_extends_time(self):
        sub = SubscriptionFactory(user=self.user, plan=self.plan, is_active=True, status=Subscription.Status.ACTIVE)
        original_ends_at = sub.ends_at
        
        payload = {
            "subscription_id": sub.id,
            "provider_payment_id": "txn_renew",
            "amount": str(self.plan.price),
            "currency": self.plan.currency,
            "succeeded": True,
            "provider": "mock"
        }
        SubscriptionService.process_webhook_payment(payload)
        
        sub.refresh_from_db()
        # Should be extended by 30 days
        self.assertEqual(sub.ends_at, original_ends_at + timedelta(days=self.plan.duration_days))
        self.assertTrue(sub.is_active)

    # 1.4 Expired Then Paid
    def test_expired_subscription_resets_on_payment(self):
        sub = SubscriptionFactory(user=self.user, plan=self.plan, is_active=False, status=Subscription.Status.EXPIRED)
        # Ends at in the past
        sub.ends_at = timezone.now() - timedelta(days=5)
        sub.save()
        
        payload = {
            "subscription_id": sub.id,
            "provider_payment_id": "txn_expired_renew",
            "amount": str(self.plan.price),
            "currency": self.plan.currency,
            "succeeded": True,
            "provider": "mock"
        }
        SubscriptionService.process_webhook_payment(payload)
        
        sub.refresh_from_db()
        # Should be reset to now + duration, not old_date + duration
        now = timezone.now()
        expected_ends_at = now + timedelta(days=self.plan.duration_days)
        # Check within a second to account for execution time
        self.assertTrue(abs((sub.ends_at - expected_ends_at).total_seconds()) < 2)
        self.assertTrue(sub.is_active)

    # 1.5 Cancel Subscription
    def test_cancel_subscription(self):
        sub = SubscriptionFactory(user=self.user, plan=self.plan, is_active=True, status=Subscription.Status.ACTIVE)
        sub.cancel()
        
        self.assertEqual(sub.status, Subscription.Status.CANCELLED)
        self.assertFalse(sub.is_active)

    # 1.6 Expire Logic
    def test_expire_subscription(self):
        sub = SubscriptionFactory(user=self.user, plan=self.plan, is_active=True, status=Subscription.Status.ACTIVE)
        sub.expire()
        
        self.assertEqual(sub.status, Subscription.Status.EXPIRED)
        self.assertFalse(sub.is_active)
