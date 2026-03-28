from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SubscriptionPlan(models.Model):
    """Defines available subscription plans.

    Use this table instead of TextChoices for flexibility in production.
    """

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    duration_days = models.PositiveIntegerField(help_text="Length of plan in days")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="KGS")
    is_active = models.BooleanField(default=True)
    features = models.JSONField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-price", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True, help_text="When this subscription will expire")
    last_payment_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["ends_at"]),
        ]
        constraints = [
            # Allow only one active subscription per user (Postgres partial unique index).
            models.UniqueConstraint(fields=["user"], condition=Q(is_active=True), name="unique_active_subscription_per_user"),
        ]

    def __str__(self) -> str:
        # Use user's repr if nickname missing
        nickname = getattr(self.user, "nickname", None) or str(self.user)
        return f"{nickname} - {self.plan.code} ({self.status})"

    def clean(self):
        # Basic validation
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise models.ValidationError({"ends_at": "ends_at must be >= starts_at"})

    def save(self, *args, **kwargs):
        # Ensure ends_at defaults to starts_at + plan.duration_days when not provided
        if not self.ends_at and self.plan and self.starts_at:
            self.ends_at = self.starts_at + timedelta(days=self.plan.duration_days)

        # Keep is_active and status consistent
        if self.is_active and self.status != self.Status.ACTIVE:
            self.status = self.Status.ACTIVE
        if not self.is_active and self.status == self.Status.ACTIVE:
            self.status = self.Status.EXPIRED

        super().save(*args, **kwargs)

    def activate(self, starts_at: timezone.datetime | None = None) -> None:
        self.starts_at = starts_at or timezone.now()
        self.ends_at = self.starts_at + timedelta(days=self.plan.duration_days)
        self.is_active = True
        self.status = self.Status.ACTIVE
        self.save()

    def cancel(self) -> None:
        self.is_active = False
        self.status = self.Status.CANCELLED
        self.save()

    def expire(self) -> None:
        self.is_active = False
        self.status = self.Status.EXPIRED
        self.save()

    def renew(self, by_days: int | None = None) -> None:
        """Extend subscription by plan.duration_days or by_days if provided."""
        delta_days = by_days or self.plan.duration_days
        if not self.ends_at:
            self.ends_at = timezone.now() + timedelta(days=delta_days)
        else:
            self.ends_at = self.ends_at + timedelta(days=delta_days)
        self.is_active = True
        self.status = self.Status.ACTIVE
        self.save()


class SubscriptionPayment(models.Model):
    """Record of payments for subscriptions. Acts as payment / invoice history.

    When a payment succeeds, the related subscription can be updated (last_payment_date,
    is_active, ends_at extension) so the subscription state is derived from the payment history.
    """

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_payments")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KGS")
    provider = models.CharField(max_length=100, blank=True, null=True)
    provider_payment_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    succeeded = models.BooleanField(default=False, db_index=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Payment {self.pk} for {self.user} - {self.amount} {self.currency} ({'OK' if self.succeeded else 'PENDING'})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if self.succeeded and not self.paid_at:
            self.paid_at = timezone.now()

        super().save(*args, **kwargs)

        # Post-save: if payment succeeded then update subscription accordingly
        if self.succeeded:
            sub = self.subscription
            # update last payment date
            sub.last_payment_date = self.paid_at
            # ensure subscription is active
            sub.is_active = True
            sub.status = sub.Status.ACTIVE

            # extend subscription ends_at if payment corresponds to a plan
            plan_days = None
            if self.plan and self.plan.duration_days:
                plan_days = self.plan.duration_days
            elif sub.plan and sub.plan.duration_days:
                plan_days = sub.plan.duration_days

            if plan_days:
                now = timezone.now()
                if not sub.ends_at or sub.ends_at < now:
                    sub.ends_at = now + timedelta(days=plan_days)
                else:
                    sub.ends_at = sub.ends_at + timedelta(days=plan_days)

            sub.save()
