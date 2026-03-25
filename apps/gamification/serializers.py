from rest_framework import serializers

from apps.gamification.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ("id", "activity_type", "delta_points", "created_at")
        read_only_fields = fields
