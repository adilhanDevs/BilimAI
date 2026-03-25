from rest_framework import serializers

from apps.subscription.models import Subscription
from apps.subscription.services.subscription_service import SubscriptionService


class SubscriptionSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    last_payment_date = serializers.DateTimeField(required=False)

    class Meta:
        model = Subscription
        fields = ("id", "user", "plan_type", "is_active", "last_payment_date", "created_at")
        read_only_fields = ("id", "user", "is_active", "created_at")

    def create(self, validated_data):
        user = self.context["request"].user
        return SubscriptionService.create_subscription(
            user=user,
            plan_type=validated_data["plan_type"],
            last_payment_date=validated_data.get("last_payment_date"),
        )
