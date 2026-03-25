from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_type", "delta_points", "created_at")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
