from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    ordering = ("-created_at",)
    list_display = (
        "nickname",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "points",
        "level",
        "created_at",
    )
    search_fields = ("nickname", "email", "first_name", "last_name")
    list_filter = ("is_staff", "is_active")
    readonly_fields = ("last_login", "created_at")

    fieldsets = (
        (None, {"fields": ("nickname", "email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name")}),
        (
            "Gamification",
            {"fields": ("points", "level", "streak", "last_streak_date", "monthly_reward_unlocked")},
        ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("nickname", "email", "password1", "password2", "first_name", "last_name"),
            },
        ),
    )
