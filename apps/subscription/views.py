from rest_framework import permissions, viewsets
from drf_spectacular.utils import extend_schema, OpenApiTypes
from common.serializers import ApiResponseSerializer

from common.responses import api_response

from .models import Subscription
from .serializers import SubscriptionSerializer
from .services.subscription_service import SubscriptionService


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related("user")

    @extend_schema(responses=ApiResponseSerializer)
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        for sub in queryset:
            SubscriptionService.sync_subscription_flags(sub)
        serializer = self.get_serializer(queryset, many=True)
        return api_response(data=serializer.data)

    @extend_schema(responses=ApiResponseSerializer)
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        SubscriptionService.sync_subscription_flags(instance)
        serializer = self.get_serializer(instance)
        return api_response(data=serializer.data)

    @extend_schema(request=SubscriptionSerializer, responses={201: ApiResponseSerializer})
    def create(self, request, *args, **kwargs):
        from rest_framework import status

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return api_response(data=serializer.data, status_code=status.HTTP_201_CREATED)
