from rest_framework import serializers

from apps.subscription.models import Subscription, SubscriptionPlan, SubscriptionPayment
from apps.subscription.services.subscription_service import SubscriptionService


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "name", "code", "duration_days", "price", "currency", "features")
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        source="plan",
        write_only=True
    )
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id", "user", "plan_id", "plan", "status", 
            "starts_at", "ends_at", "last_payment_date", "is_active", "created_at"
        )
        read_only_fields = (
            "id", "user", "plan", "status", 
            "starts_at", "ends_at", "last_payment_date", "is_active", "created_at"
        )

    def create(self, validated_data):
        user = self.context["request"].user
        plan = validated_data["plan"]
        return SubscriptionService.create_subscription(user=user, plan=plan)


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = (
            "id", "subscription", "amount", "currency", 
            "provider", "succeeded", "paid_at"
        )
        read_only_fields = fields
