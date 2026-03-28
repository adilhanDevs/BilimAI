from typing import Dict, Any
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.subscription.services.subscription_service import SubscriptionService
from apps.ai.models import DailyChatUsage


class ChatLimitService:
    @classmethod
    def get_limits(cls) -> Dict[str, int]:
        return {
            "subscribed": getattr(settings, "CHAT_LIMIT_SUBSCRIBED", 100),
            "free_auth": getattr(settings, "CHAT_LIMIT_FREE_AUTH", 10),
            "guest": getattr(settings, "CHAT_LIMIT_GUEST", 5),
        }

    @classmethod
    def get_guest_key(cls, request) -> str:
        """
        Extract the most accurate guest identifier from the request.
        Priority:
        1. X-Guest-Id (from frontend localStorage)
        2. HTTP_X_FORWARDED_FOR (for proxies)
        3. REMOTE_ADDR (fallback)
        """
        guest_id = request.headers.get("X-Guest-Id", "").strip()
        if guest_id:
            return guest_id

        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "").strip()
        if x_forwarded_for:
            # Proxies can append multiple IPs, take the first one (client IP)
            return x_forwarded_for.split(",")[0].strip()

        remote_addr = request.META.get("REMOTE_ADDR", "").strip()
        if remote_addr:
            return remote_addr

        # Safe fallback if everything is missing
        return "unknown"

    @classmethod
    def get_user_limit(cls, user) -> int:
        limits = cls.get_limits()
        if not user or not user.is_authenticated:
            return limits["guest"]
        
        if SubscriptionService.user_has_active_subscription(user):
            return limits["subscribed"]
        
        return limits["free_auth"]

    @classmethod
    def check_and_increment_usage(cls, request) -> Dict[str, Any]:
        """
        Atomically checks and increments the daily chat usage for the requester.
        Returns a dict: {'allowed': bool, 'limit': int, 'used': int, 'remaining': int}
        """
        user = request.user if request.user and request.user.is_authenticated else None
        guest_key = None if user else cls.get_guest_key(request)
        
        limit = cls.get_user_limit(user)
        today = timezone.localdate()

        user_kwargs = {}
        if user:
            user_kwargs["user"] = user
        else:
            user_kwargs["guest_key"] = guest_key

        with transaction.atomic():
            # Get or create usage for today locking the row
            usage, created = DailyChatUsage.objects.select_for_update().get_or_create(
                date=today,
                **user_kwargs,
                defaults={"count": 0}
            )

            # If over or at limit, do not increment
            if usage.count >= limit:
                return {
                    "allowed": False,
                    "limit": limit,
                    "used": usage.count,
                    "remaining": 0,
                }

            # Increment usage
            usage.count += 1
            usage.save(update_fields=["count"])

            return {
                "allowed": True,
                "limit": limit,
                "used": usage.count,
                "remaining": max(0, limit - usage.count),
            }
