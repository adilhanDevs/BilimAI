from decimal import Decimal
import logging
from django.utils import timezone
from apps.subscription.models import Subscription, SubscriptionPayment, SubscriptionPlan

logger = logging.getLogger(__name__)

class SubscriptionService:
    @staticmethod
    def create_subscription(user, plan: SubscriptionPlan) -> Subscription:
        # PENDING by default
        return Subscription.objects.create(
            user=user,
            plan=plan,
            status=Subscription.Status.PENDING,
            is_active=False,
            starts_at=timezone.now(),
        )

    @staticmethod
    def user_has_active_subscription(user) -> bool:
        """Check if a User has an active subscription."""
        if not user or not user.is_authenticated:
            return False
        return user.subscriptions.filter(is_active=True).exists()

    @staticmethod
    def process_webhook_payment(data: dict) -> SubscriptionPayment | None:
        """
        Process incoming webhook from payment provider.
        """
        subscription_id = data.get("subscription_id")
        provider_payment_id = data.get("provider_payment_id")
        amount = Decimal(str(data.get("amount", "0")))
        currency = data.get("currency", "KGS")
        succeeded = data.get("succeeded", False)
        provider = data.get("provider", "mock_provider")

        if not subscription_id or not provider_payment_id:
            logger.warning("Webhook missing subscription_id or provider_payment_id")
            raise ValueError("Invalid payload: missing fields")

        # Idempotency check
        existing_payment = SubscriptionPayment.objects.filter(
            provider_payment_id=provider_payment_id
        ).first()

        if existing_payment:
            logger.info("Payment %s already processed", provider_payment_id)
            return existing_payment

        try:
            subscription = Subscription.objects.select_related("plan").get(id=subscription_id)
        except Subscription.DoesNotExist:
            logger.error("Subscription %s not found for payment", subscription_id)
            raise ValueError("Subscription not found")

        # Validate amount (assuming strict match required for mock/simple implementation)
        if amount != subscription.plan.price:
            logger.warning("Webhook amount %s does not match plan price %s", amount, subscription.plan.price)
            # In production we might still save the payment as failed, but here we enforce match
            succeeded = False

        # Create payment record
        payment = SubscriptionPayment(
            subscription=subscription,
            user=subscription.user,
            plan=subscription.plan,
            amount=amount,
            currency=currency,
            provider=provider,
            provider_payment_id=provider_payment_id,
            succeeded=succeeded,
        )
        
        from django.db import transaction
        with transaction.atomic():
            payment.save()
            # payment.save() model method handles the subscription activation and date extension!

        return payment

    @staticmethod
    def sync_subscription_flags(subscription: Subscription) -> Subscription:
        now = timezone.now()
        if subscription.is_active and subscription.ends_at and subscription.ends_at < now:
            subscription.expire()
        return subscription
