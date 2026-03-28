from django.contrib import admin

from .models import Subscription, SubscriptionPlan, SubscriptionPayment


admin.site.register(SubscriptionPlan)

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
