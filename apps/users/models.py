from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, nickname, email, password=None, **extra_fields):
        if not nickname:
            raise ValueError("The nickname must be set")
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(nickname=nickname, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, nickname, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(nickname, email, password, **extra_fields)







class User(AbstractBaseUser, PermissionsMixin):
    nickname = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0, help_text="Highest streak achieved")
    last_streak_date = models.DateField(null=True, blank=True)
    monthly_reward_unlocked = models.BooleanField(default=False)

    # Language Preferences
    native_language = models.CharField(max_length=10, default="ky", help_text="User's native language")
    target_language = models.CharField(max_length=10, default="tr", help_text="Language the user is learning")

    # Learning Progress & Stats
    onboarding_completed = models.BooleanField(default=False)
    current_course = models.ForeignKey(
        "lessons.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_users",
    )
    daily_goal_xp = models.IntegerField(default=20, help_text="Daily XP goal set by user")
    total_lessons_completed = models.IntegerField(default=0)
    current_timezone = models.CharField(max_length=100, null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "nickname"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.nickname
