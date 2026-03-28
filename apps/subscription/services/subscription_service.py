from decimal import Decimal
import logging
from django.utils import timezone
from apps.subscription.models import Subscription, SubscriptionPayment, SubscriptionPlan

logger = logging.getLogger(__name__)

class SubscriptionService:
    @staticmethod
    def user_has_active_subscription(user) -> bool:
        """Check if a User has an active subscription."""
        if not user or not user.is_authenticated:
            return False
        return user.subscriptions.filter(is_active=True).exists()

    @staticmethod
    def process_frontend_payment(user, data: dict) -> SubscriptionPayment | None:
        """
        Process a confirmed payment payload from the frontend webhook.
        Always called with an authenticated user.
        Atomically creates Subscription + SubscriptionPayment.
        """
        plan_id = data.get("plan_id")
        provider_payment_id = data.get("provider_payment_id")
        amount = Decimal(str(data.get("amount", "0")))
        currency = data.get("currency", "KGS")
        succeeded = data.get("succeeded", False)
        provider = data.get("provider", "mock_provider")

        if not plan_id or not provider_payment_id:
            logger.warning("Payment missing plan_id or provider_payment_id")
            raise ValueError("Invalid payload: plan_id and provider_payment_id are required")

        if not user or not user.is_authenticated:
            raise ValueError("Authenticated user is required")

        # Idempotency check
        existing_payment = SubscriptionPayment.objects.filter(
            provider_payment_id=provider_payment_id
        ).first()
        if existing_payment:
            logger.info("Payment %s already processed", provider_payment_id)
            return existing_payment

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            logger.error("Plan %s not found", plan_id)
            raise ValueError("Subscription Plan not found")

        # Validate amount
        if amount != plan.price:
            logger.warning("Payment amount %s does not match plan price %s", amount, plan.price)
            succeeded = False

        from django.db import transaction
        with transaction.atomic():
            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                status=Subscription.Status.PENDING,
                is_active=False,
                starts_at=timezone.now(),
            )
            payment = SubscriptionPayment(
                subscription=subscription,
                user=user,
                plan=plan,
                amount=amount,
                currency=currency,
                provider=provider,
                provider_payment_id=provider_payment_id,
                succeeded=succeeded,
            )
            payment.save()
            # payment.save() activates the subscription if succeeded=True

        return payment


    @staticmethod
    def sync_subscription_flags(subscription: Subscription) -> Subscription:
        now = timezone.now()
        if subscription.is_active and subscription.ends_at and subscription.ends_at < now:
            subscription.expire()
        return subscription
