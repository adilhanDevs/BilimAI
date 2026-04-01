from django.test import TestCase
from apps.subscription.models import Subscription, SubscriptionPayment
from apps.subscription.services.subscription_service import SubscriptionService
from .factories import UserFactory, SubscriptionPlanFactory, SubscriptionFactory

class PaymentWebhookTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(price=150.00)
        self.sub = SubscriptionFactory(user=self.user, plan=self.plan)

    # 2.1 Successful Webhook
    def test_webhook_success_flow(self):
        payload = {
            "subscription_id": str(self.sub.id),
            "provider_payment_id": "txn_success",
            "amount": "150.00",
            "currency": "KGS",
            "succeeded": True,
            "provider": "mock"
        }
        url = "/api/subscriptions/webhook/"
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.is_active)
        self.assertEqual(self.sub.status, Subscription.Status.ACTIVE)
        
        payment = SubscriptionPayment.objects.get(provider_payment_id="txn_success")
        self.assertTrue(payment.succeeded)

    # 2.2 Idempotency
    def test_webhook_idempotency(self):
        payload = {
            "subscription_id": str(self.sub.id),
            "provider_payment_id": "txn_idempotency",
            "amount": "150.00",
            "currency": "KGS",
            "succeeded": True,
            "provider": "mock"
        }
        url = "/api/subscriptions/webhook/"
        
        r1 = self.client.post(url, payload, format='json')
        self.assertEqual(r1.status_code, 200)
        self.sub.refresh_from_db()
        ends_at_after_first = self.sub.ends_at
        
        # Call again
        r2 = self.client.post(url, payload, format='json')
        self.assertEqual(r2.status_code, 200)
        self.sub.refresh_from_db()
        
        self.assertEqual(self.sub.ends_at, ends_at_after_first)
        self.assertEqual(SubscriptionPayment.objects.filter(provider_payment_id="txn_idempotency").count(), 1)

    # 2.3 Invalid Signature (Mock signature verification - for now we test ValueError raise)
    def test_webhook_invalid_signature(self):
        # We don't have signature logic yet, but if it's missing subscription_id it fails
        payload = {
            "provider_payment_id": "txn_invalid",
            "amount": "150.00",
        }
        with self.assertRaisesMessage(ValueError, "Invalid payload: missing fields"):
            SubscriptionService.process_webhook_payment(payload)
            
        self.assertEqual(SubscriptionPayment.objects.count(), 0)

    # 2.4 Wrong Amount
    def test_webhook_amount_mismatch(self):
        payload = {
            "subscription_id": self.sub.id,
            "provider_payment_id": "txn_wrong_amount",
            "amount": "100.00", # Plan is 150
            "currency": "KGS",
            "succeeded": True,
            "provider": "mock"
        }
        
        payment = SubscriptionService.process_webhook_payment(payload)
        # Should reject as not succeeded
        self.assertFalse(payment.succeeded)
        
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)
        self.assertEqual(self.sub.status, Subscription.Status.PENDING)

    # 2.5 Unknown Subscription
    def test_webhook_invalid_subscription(self):
        payload = {
            "subscription_id": 999999,
            "provider_payment_id": "txn_unknown_sub",
            "amount": "150.00",
            "currency": "KGS",
            "succeeded": True,
            "provider": "mock"
        }
        
        with self.assertRaisesMessage(ValueError, "Subscription not found"):
            SubscriptionService.process_webhook_payment(payload)
            
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    # 2.6 Duplicate provider_payment_id
    def test_duplicate_provider_payment_id(self):
        # Implicitly tested in idempotency, but let's test specifically that state does not change
        payload = {
            "subscription_id": self.sub.id,
            "provider_payment_id": "txn_dup2",
            "amount": "150.00",
            "currency": "KGS",
            "succeeded": True,
            "provider": "mock"
        }
        SubscriptionService.process_webhook_payment(payload)
        count = SubscriptionPayment.objects.filter(provider_payment_id="txn_dup2").count()
        self.assertEqual(count, 1)
        
        # Sending with different successful payload but same txn id returns existing and ignores new data
        payload["amount"] = "200.00"
        SubscriptionService.process_webhook_payment(payload)
        count = SubscriptionPayment.objects.filter(provider_payment_id="txn_dup2").count()
        self.assertEqual(count, 1)
