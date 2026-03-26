📄 TESTING PRD
Subscription & Payment System (Production-Level)
🎯 Objective

Design and implement a comprehensive, production-grade test suite for the subscription and payment system to ensure:

Data integrity
Business logic correctness
Security of webhook processing
Idempotency of payments
Stability under edge cases
🧠 Testing Philosophy

The system follows:

Payment → Source of Truth
Subscription → Derived State

👉 Therefore:

Tests MUST prioritize payment-driven flows
Direct subscription manipulation is secondary
Webhook is the critical entry point
🧱 Test Structure
tests/
├── test_subscription_service.py
├── test_payment_webhook.py
├── test_subscription_api.py
├── test_constraints.py
├── test_edge_cases.py
1️⃣ CORE SERVICE TESTS
File: test_subscription_service.py
✅ 1.1 Create Subscription
def test_create_subscription():

Goal:

Ensure subscription is created correctly

Assertions:

status == PENDING
is_active == False
ends_at is calculated
user assigned
✅ 1.2 Activate Subscription via Payment
def test_payment_activates_subscription():

Flow:

create subscription
simulate successful payment

Assertions:

status == ACTIVE
is_active == True
last_payment_date set
ends_at extended correctly
✅ 1.3 Renewal Logic
def test_subscription_renewal_extends_time():

Case:

subscription still active

Assertions:

ends_at += duration
no reset to now
✅ 1.4 Expired Then Paid
def test_expired_subscription_resets_on_payment():

Case:

ends_at < now

Assertions:

ends_at = now + duration
NOT += old value
✅ 1.5 Cancel Subscription
def test_cancel_subscription():

Assertions:

status == CANCELLED
is_active == False
✅ 1.6 Expire Logic
def test_expire_subscription():

Assertions:

status == EXPIRED
is_active == False
2️⃣ WEBHOOK TESTS (CRITICAL)
File: test_payment_webhook.py
🔥 2.1 Successful Webhook
def test_webhook_success_flow():

Flow:

send valid webhook payload

Assertions:

payment.succeeded == True
subscription activated
ends_at updated
🔥 2.2 Idempotency
def test_webhook_idempotency():

Flow:

send same webhook twice

Assertions:

only 1 payment created
ends_at extended only once
🔥 2.3 Invalid Signature
def test_webhook_invalid_signature():

Assertions:

403 response
no payment created
no subscription update
🔥 2.4 Wrong Amount
def test_webhook_amount_mismatch():

Assertions:

reject webhook
no activation
🔥 2.5 Unknown Subscription
def test_webhook_invalid_subscription():

Assertions:

404 or ignored
no crash
🔥 2.6 Duplicate provider_payment_id
def test_duplicate_provider_payment_id():

Assertions:

only first processed
second ignored
3️⃣ API TESTS
File: test_subscription_api.py
✅ 3.1 Get Plans
def test_get_plans():

Assertions:

returns only active plans
✅ 3.2 Create Subscription
def test_create_subscription_api():

Assertions:

status == PENDING
user assigned correctly
✅ 3.3 Get Current Subscription
def test_get_me_subscription():

Assertions:

latest subscription returned
❌ 3.4 Unauthorized Access
def test_unauthorized_access():

Assertions:

401
4️⃣ DATABASE CONSTRAINT TESTS
File: test_constraints.py
🔒 4.1 Only One Active Subscription
def test_only_one_active_subscription():

Flow:

create active subscription
try creating second active

Assertions:

IntegrityError
🔒 4.2 Foreign Key Integrity
def test_subscription_plan_protection():

Assertions:

cannot delete plan in use
5️⃣ EDGE CASE TESTS
File: test_edge_cases.py
⚠️ 5.1 Payment Without Plan
def test_payment_without_plan_fallback():

Assertions:

fallback to subscription.plan
⚠️ 5.2 ends_at None
def test_missing_ends_at():

Assertions:

auto-calculated
⚠️ 5.3 Timezone Safety
def test_timezone_handling():

Assertions:

timezone-aware datetime
⚠️ 5.4 Concurrent Webhooks
def test_concurrent_webhooks():

Goal:

simulate race condition

Assertions:

no duplicate extension
⚠️ 5.5 Payment Created but Not Succeeded
def test_unsuccessful_payment():

Assertions:

subscription unchanged
🧪 TEST DATA FACTORIES

Use:

UserFactory
SubscriptionPlanFactory
SubscriptionFactory
SubscriptionPaymentFactory
⚙️ TESTING TOOLS

Recommended stack:

pytest
pytest-django
factory_boy
freezegun (for time tests)
🧠 COVERAGE TARGET
Layer	Coverage
Service	100%
Webhook	100%
API	90%+
Models	95%+
🔥 CRITICAL RULES
❗ NEVER:
Trust webhook blindly
Skip idempotency tests
Skip amount validation
✅ ALWAYS:
Test duplicate events
Test expired logic
Test race conditions
🚀 FINAL EXPECTED RESULT

After implementing this PRD:

System is fully protected against payment fraud
Subscription logic is deterministic
Webhook is idempotent and safe
Backend is production-grade reliable