from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiTypes
from common.serializers import ApiResponseSerializer

from common.permissions import HasActiveSubscription
from common.responses import api_response

from .models import ChatMessage, ChatSession
from .serializers import ChatMessageSerializer, ChatRequestSerializer, ChatSessionSerializer
from .services.chat_service import ChatService, ChatServiceError


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    @extend_schema(
        request=ChatRequestSerializer,
        responses={201: ApiResponseSerializer, 502: ApiResponseSerializer},
    )
    def post(self, request, *args, **kwargs): 
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_text = ser.validated_data["message"]
        session_id = ser.validated_data.get("session_id")

        if session_id:
            try:
                session = ChatSession.objects.get(pk=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                return api_response(
                    success=False,
                    data=None,
                    error={"detail": "Invalid session_id."},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            session = ChatSession.objects.filter(user=request.user).order_by("-updated_at", "-created_at").first()
            if not session:
                session = ChatSession.objects.create(user=request.user, title="")

        prior = list(
            ChatMessage.objects.filter(user=request.user, session=session)
            .order_by("-created_at")[:20]
            .values("message", "response", "created_at")
        )
        history: list[dict[str, str]] = []
        for row in reversed(prior):
            history.append({"role": "user", "content": row["message"]})
            history.append({"role": "assistant", "content": row["response"]})

        try:
            reply = ChatService.generate_reply(user_text, history)
        except ChatServiceError as exc:
            return api_response(
                success=False,
                data=None,
                error={"detail": str(exc)},
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        chat = ChatMessage.objects.create(user=request.user, session=session, message=user_text, response=reply)
        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])
        return api_response(data=ChatMessageSerializer(chat).data, status_code=status.HTTP_201_CREATED)


class ChatHistoryView(ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def get_queryset(self):
        request = self.request
        session_id = request.query_params.get("session_id")
        show_all = str(request.query_params.get("all", "")).lower() in ("1", "true", "yes")

        qs = ChatMessage.objects.filter(user=request.user).select_related("user", "session").order_by("-created_at")
        if show_all:
            return qs

        if session_id:
            return qs.filter(session_id=session_id)

        latest_session = ChatSession.objects.filter(user=request.user).order_by("-updated_at", "-created_at").first()
        if not latest_session:
            return qs.none()
        return qs.filter(session=latest_session)

    @extend_schema(responses=ApiResponseSerializer)
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "error": None})


class ChatSessionView(ListCreateAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by("-updated_at", "-created_at")

    def create(self, request, *args, **kwargs):
        title = str(request.data.get("title", "")).strip()
        session = ChatSession.objects.create(user=request.user, title=title)
        return api_response(data=ChatSessionSerializer(session).data, status_code=status.HTTP_201_CREATED)
