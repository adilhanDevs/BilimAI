from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "nickname",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "created_at",
            "points",
            "level",
            "streak",
            "monthly_reward_unlocked",
        )
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ("nickname", "email", "first_name", "last_name", "password", "password2")

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs


class LoginSerializer(serializers.Serializer):
    nickname = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
