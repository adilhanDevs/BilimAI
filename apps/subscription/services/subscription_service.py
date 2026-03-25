import logging

from django.utils import timezone

from apps.subscription.models import Subscription

logger = logging.getLogger(__name__)

# Per product spec: subscription is invalid after 30 days from last payment.
ACTIVE_WINDOW_DAYS = 30


class SubscriptionService:
    @staticmethod
    def create_subscription(user, plan_type: str, last_payment_date=None) -> Subscription:
        allowed = {choice.value for choice in Subscription.PlanType}
        if plan_type not in allowed:
            raise ValueError("Invalid plan_type.")
        when = last_payment_date or timezone.now()
        return Subscription.objects.create(
            user=user,
            plan_type=plan_type,
            is_active=True,
            last_payment_date=when,
        )

    @staticmethod
    def is_within_payment_window(subscription: Subscription) -> bool:
        now = timezone.now()
        delta = now - subscription.last_payment_date
        return delta.days <= ACTIVE_WINDOW_DAYS

    @staticmethod
    def sync_subscription_flags(subscription: Subscription) -> Subscription:
        valid = SubscriptionService.is_within_payment_window(subscription)
        if subscription.is_active != valid:
            subscription.is_active = valid
            subscription.save(update_fields=["is_active"])
            logger.debug("Subscription %s is_active=%s", subscription.pk, valid)
        return subscription

    @staticmethod
    def user_has_active_subscription(user) -> bool:
        subscription = (
            Subscription.objects.filter(user=user).select_related("user").order_by("-created_at").first()
        )
        if not subscription:
            return False
        SubscriptionService.sync_subscription_flags(subscription)
        return subscription.is_active
