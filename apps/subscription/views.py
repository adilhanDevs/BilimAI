from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiTypes
from common.serializers import ApiResponseSerializer
from common.responses import api_response
import logging

from .models import Subscription, SubscriptionPlan
from .serializers import SubscriptionSerializer, SubscriptionPlanSerializer
from .services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True).order_by("price")

    @extend_schema(responses=ApiResponseSerializer)
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return api_response(data=serializer.data)

    @extend_schema(responses=ApiResponseSerializer)
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_response(data=serializer.data)


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related("plan")

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

    @extend_schema(responses=ApiResponseSerializer)
    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get the current active or most recent subscription for the user."""
        subscription = self.get_queryset().order_by("-is_active", "-created_at").first()
        if not subscription:
            return api_response(data=None)

        SubscriptionService.sync_subscription_flags(subscription)
        serializer = self.get_serializer(subscription)
        return api_response(data=serializer.data)

    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses=ApiResponseSerializer,
        description=(
            "Receive a confirmed payment result from the frontend webhook and "
            "create Subscription + SubscriptionPayment atomically.\n\n"
            "**Payload fields:**\n"
            "- `plan_id` (int): ID of the SubscriptionPlan\n"
            "- `provider_payment_id` (str): Unique payment ID from the provider\n"
            "- `amount` (str): Amount paid — must match plan price\n"
            "- `currency` (str): Currency code, e.g. `KGS`\n"
            "- `succeeded` (bool): Whether the payment succeeded\n"
            "- `provider` (str, optional): Payment provider name"
        ),
    )
    @action(detail=False, methods=["post"], url_path="process-payment")
    def process_payment(self, request):
        """Process payment confirmed by frontend webhook. Authenticated endpoint."""
        try:
            payment = SubscriptionService.process_frontend_payment(request.user, request.data)
            return api_response(
                data={
                    "status": "success",
                    "payment_id": payment.id if payment else None,
                    "succeeded": payment.succeeded if payment else False,
                },
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return api_response(error=str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("process_payment failed")
            return api_response(
                error="Internal server error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=ApiResponseSerializer)
    @action(detail=False, methods=["post"], url_path="create-link")
    def create_link(self, request):
        subscription_id = request.data.get("subscription_id")
        if not subscription_id:
            return api_response(error="subscription_id is required", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            subscription = Subscription.objects.get(id=subscription_id, user=request.user)
        except Subscription.DoesNotExist:
            return api_response(error="Subscription not found", status_code=status.HTTP_404_NOT_FOUND)

        payment_url = f"https://mock-provider.com/pay/{subscription.id}?amount={subscription.plan.price}&currency={subscription.plan.currency}"
        return api_response(data={"payment_url": payment_url})
