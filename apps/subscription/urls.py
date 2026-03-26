from rest_framework.routers import DefaultRouter

from .views import SubscriptionViewSet, SubscriptionPlanViewSet, PaymentViewSet

router = DefaultRouter()
router.register("plans", SubscriptionPlanViewSet, basename="subscription-plan")
router.register("payments", PaymentViewSet, basename="payment")
router.register("", SubscriptionViewSet, basename="subscription")

urlpatterns = router.urls
