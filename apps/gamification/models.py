from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    class ActivityType(models.TextChoices):
        DAILY_SESSION = "daily_session", "Daily session"
        STREAK_BONUS = "streak_bonus", "Streak bonus"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_logs")
    activity_type = models.CharField(max_length=32, choices=ActivityType.choices)
    delta_points = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.activity_type} {self.delta_points}"
