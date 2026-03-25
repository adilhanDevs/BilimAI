from rest_framework.permissions import BasePermission

from apps.subscription.services.subscription_service import SubscriptionService


class HasActiveSubscription(BasePermission):
    """Requires the authenticated user to have an active subscription."""

    message = "Active subscription required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return SubscriptionService.user_has_active_subscription(request.user)
