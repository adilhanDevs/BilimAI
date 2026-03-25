from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.users.urls")),
    path("api/subscriptions/", include("apps.subscription.urls")),
    path("api/gamification/", include("apps.gamification.urls")),
    path("api/ai/", include("apps.ai.urls")),
]
