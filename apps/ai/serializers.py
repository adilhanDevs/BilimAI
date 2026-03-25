from rest_framework import serializers

from apps.ai.models import ChatMessage


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=8000, trim_whitespace=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "message", "response", "created_at")
        read_only_fields = fields
