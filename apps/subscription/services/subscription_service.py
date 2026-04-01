from decimal import Decimal
import logging
from django.utils import timezone
from django.db import transaction
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
    def create_subscription(user, plan: SubscriptionPlan) -> Subscription:
        """Creates a pending subscription for a user."""
        return Subscription.objects.create(
            user=user,
            plan=plan,
            status=Subscription.Status.PENDING,
            is_active=False,
            starts_at=timezone.now()
        )

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
    def process_webhook_payment(payload: dict) -> SubscriptionPayment:
        """
        Process a payment webhook from an external provider.
        Idempotent and concurrent-safe.
        """
        sub_id = payload.get("subscription_id")
        provider_payment_id = payload.get("provider_payment_id")
        amount_str = payload.get("amount")
        currency = payload.get("currency", "KGS")
        succeeded = payload.get("succeeded", False)
        provider = payload.get("provider", "unknown")

        if not sub_id or not provider_payment_id or amount_str is None:
            raise ValueError("Invalid payload: missing fields")

        amount = Decimal(str(amount_str))

        # Idempotency check
        existing_payment = SubscriptionPayment.objects.filter(
            provider_payment_id=provider_payment_id
        ).first()
        if existing_payment:
            return existing_payment

        with transaction.atomic():
            try:
                # Use select_for_update for concurrency safety
                subscription = Subscription.objects.select_for_update().get(id=sub_id)
            except Subscription.DoesNotExist:
                raise ValueError("Subscription not found")

            # Validate amount against plan
            if amount != subscription.plan.price:
                logger.warning("Webhook amount mismatch for sub %s", sub_id)
                succeeded = False

            payment = SubscriptionPayment.objects.create(
                subscription=subscription,
                user=subscription.user,
                plan=subscription.plan,
                amount=amount,
                currency=currency,
                provider=provider,
                provider_payment_id=provider_payment_id,
                succeeded=succeeded,
            )
            # Subscription is updated in SubscriptionPayment.save()

        return payment

    @staticmethod
    def sync_subscription_flags(subscription: Subscription) -> Subscription:
        now = timezone.now()
        if subscription.is_active and subscription.ends_at and subscription.ends_at < now:
            subscription.expire()
        return subscription
