from django.contrib import admin

from .models import Subscription, SubscriptionPlan, SubscriptionPayment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price", "duration_days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "is_active", "starts_at", "ends_at")
    list_select_related = ("user", "plan")
    raw_id_fields = ("user",)
    list_filter = ("status", "is_active")


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ("subscription", "user", "amount", "succeeded", "paid_at")
    list_select_related = ("subscription", "user")
    raw_id_fields = ("user", "subscription")
    list_filter = ("succeeded",)
