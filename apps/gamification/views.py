from rest_framework import permissions, status
from rest_framework.views import APIView

from common.permissions import HasActiveSubscription
from common.responses import api_response

from .serializers import ActivityLogSerializer
from .services.gamification_service import GamificationService


class GamificationSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def get(self, request, *args, **kwargs):
        return api_response(data=GamificationService.summary(request.user))


class GamificationSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def post(self, request, *args, **kwargs):
        data = GamificationService.record_daily_session(request.user)
        return api_response(data=data, status_code=status.HTTP_201_CREATED)


class GamificationActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def get(self, request, *args, **kwargs):
        logs = GamificationService.recent_activity(request.user)
        serializer = ActivityLogSerializer(logs, many=True)
        return api_response(data=serializer.data)
