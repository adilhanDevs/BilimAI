from rest_framework import serializers


class ApiResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = serializers.JSONField(allow_null=True)
    error = serializers.JSONField(allow_null=True)
