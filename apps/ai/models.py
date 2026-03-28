from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-created_at")
        indexes = [models.Index(fields=["user", "updated_at"])]

    def __str__(self):
        return f"session:{self.pk} user:{self.user_id}"


class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    message = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"chat:{self.pk} user:{self.user_id}"


class DailyChatUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_chat_usages",
        null=True,
        blank=True,
    )
    guest_key = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(db_index=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                condition=models.Q(user__isnull=False),
                name="unique_user_daily_chat_usage",
            ),
            models.UniqueConstraint(
                fields=["guest_key", "date"],
                condition=models.Q(guest_key__isnull=False),
                name="unique_guest_daily_chat_usage",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["guest_key", "date"]),
        ]

    def __str__(self):
        if self.user_id:
            return f"User {self.user_id} on {self.date}: {self.count}"
        return f"Guest {self.guest_key} on {self.date}: {self.count}"
