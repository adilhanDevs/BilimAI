import factory
from django.utils import timezone
from apps.subscription.models import SubscriptionPlan, Subscription, SubscriptionPayment
from apps.users.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    nickname = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

class SubscriptionPlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionPlan

    name = factory.Sequence(lambda n: f"Plan {n}")
    code = factory.Sequence(lambda n: f"plan_{n}")
    duration_days = 30
    price = 100.00
    currency = "KGS"
    is_active = True

class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(SubscriptionPlanFactory)
    status = Subscription.Status.PENDING
    is_active = False
    starts_at = factory.LazyFunction(timezone.now)

class SubscriptionPaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionPayment

    subscription = factory.SubFactory(SubscriptionFactory)
    user = factory.SelfAttribute('subscription.user')
    plan = factory.SelfAttribute('subscription.plan')
    amount = factory.SelfAttribute('subscription.plan.price')
    currency = factory.SelfAttribute('subscription.plan.currency')
    provider = "mock_provider"
    provider_payment_id = factory.Sequence(lambda n: f"txn_{n}")
    succeeded = False
