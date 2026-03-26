from rest_framework import serializers

from apps.ai.models import ChatMessage, ChatSession


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=8000, trim_whitespace=True)
    session_id = serializers.IntegerField(required=False)


class ChatMessageSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "session_id", "message", "response", "created_at")
        read_only_fields = fields


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ("id", "title", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
