from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan_type", "is_active", "last_payment_date", "created_at")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
