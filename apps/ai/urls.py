from django.urls import path

from .views import ChatHistoryView, ChatSessionView, ChatView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("history/", ChatHistoryView.as_view(), name="ai-history"),
    path("sessions/", ChatSessionView.as_view(), name="ai-sessions"),
]
