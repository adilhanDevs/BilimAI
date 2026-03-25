from django.conf import settings
from django.db import models


class Subscription(models.Model):
    class PlanType(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan_type = models.CharField(max_length=10, choices=PlanType.choices)
    is_active = models.BooleanField(default=True)
    last_payment_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.nickname} - {self.plan_type}"
