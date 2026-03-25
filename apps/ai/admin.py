from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    search_fields = ("message", "response", "user__nickname")
