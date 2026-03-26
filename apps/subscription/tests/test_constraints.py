from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from apps.subscription.models import Subscription, SubscriptionPlan
from .factories import UserFactory, SubscriptionPlanFactory, SubscriptionFactory

class ConstraintTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory()
        
    def test_only_one_active_subscription(self):
        sub1 = SubscriptionFactory(user=self.user, plan=self.plan, is_active=True, status=Subscription.Status.ACTIVE)
        
        sub2 = SubscriptionFactory(user=self.user, plan=self.plan, is_active=False, status=Subscription.Status.PENDING)
        
        with self.assertRaises(IntegrityError):
            sub2.is_active = True
            sub2.status = Subscription.Status.ACTIVE
            sub2.save()

    def test_subscription_plan_protection(self):
        sub = SubscriptionFactory(user=self.user, plan=self.plan)
        
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.plan.delete()
