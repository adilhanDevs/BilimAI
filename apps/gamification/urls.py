from django.urls import path

from .views import GamificationActivityView, GamificationSessionView, GamificationSummaryView

urlpatterns = [
    path("me/", GamificationSummaryView.as_view(), name="gamification-me"),
    path("session/", GamificationSessionView.as_view(), name="gamification-session"),
    path("activity/", GamificationActivityView.as_view(), name="gamification-activity"),
]
