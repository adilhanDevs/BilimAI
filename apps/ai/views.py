from rest_framework import permissions, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasActiveSubscription
from common.responses import api_response

from .models import ChatMessage
from .serializers import ChatMessageSerializer, ChatRequestSerializer
from .services.chat_service import ChatService, ChatServiceError


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def post(self, request, *args, **kwargs):
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_text = ser.validated_data["message"]

        prior = list(
            ChatMessage.objects.filter(user=request.user)
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

        chat = ChatMessage.objects.create(user=request.user, message=user_text, response=reply)
        return api_response(data=ChatMessageSerializer(chat).data, status_code=status.HTTP_201_CREATED)


class ChatHistoryView(ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]

    def get_queryset(self):
        return ChatMessage.objects.filter(user=self.request.user).select_related("user").order_by("-created_at")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "error": None})
