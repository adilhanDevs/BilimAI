📄 PRODUCT REQUIREMENTS DOCUMENT (PRD)
🧩 Project Title

Subscription & Payment System Refactor (Production Upgrade)

🎯 Objective

Refactor the existing subscription and payment system to align with the new production-ready data models and architecture.

The current implementation is based on a simplified model and must be upgraded to:

Support flexible subscription plans
Integrate external payment providers via payment links
Handle webhook-based payment confirmation
Maintain accurate subscription lifecycle state
Ensure data consistency and scalability
🏗️ Scope
In Scope
Refactor serializers to match new models
Refactor API views to support new logic
Implement payment flow (payment link + webhook)
Ensure subscription lifecycle correctness
Backward compatibility (if needed)
Out of Scope (optional future)
UI/Frontend changes
Advanced billing (proration, coupons)
Multi-provider routing
🧠 System Overview

The system is composed of three main entities:

1. SubscriptionPlan

Defines available pricing plans.

2. Subscription

Represents a user's active or inactive subscription.

3. SubscriptionPayment

Tracks payment history and triggers subscription updates.

🔄 Core Business Flow
User selects plan
    ↓
Subscription created (PENDING)
    ↓
Backend generates payment link
    ↓
User completes payment on provider page
    ↓
Provider sends webhook
    ↓
Backend verifies webhook
    ↓
SubscriptionPayment created/updated
    ↓
Subscription activated or extended
🧱 Data Model (Already Implemented)

Based on current models:

Key Features:
Subscription duration derived from plan
One active subscription per user (DB constraint)
Automatic subscription extension on payment
Payment history tracking
Status lifecycle: PENDING → ACTIVE → EXPIRED/CANCELLED
🔧 Required Refactor Tasks
1. SERIALIZERS UPDATE
❗ Problem

Old serializers are based on outdated models.

✅ Requirements
SubscriptionPlanSerializer
Read-only for users
Include:
name
code
price
duration_days
features
SubscriptionSerializer
Should include:
plan (nested or id)
status
starts_at
ends_at
is_active
Must NOT allow:
manual setting of is_active
manual setting of ends_at
SubscriptionPaymentSerializer
Used for internal/admin or webhook processing
Fields:
amount
currency
provider
succeeded
paid_at
2. API ENDPOINTS (REFORM)
📌 1. Get Plans
GET /api/subscriptions/plans/

Returns all active plans.

📌 2. Create Subscription
POST /api/subscriptions/

Input:

{
  "plan_id": 1
}

Logic:

Create subscription with:
status = PENDING
is_active = False
📌 3. Get Current Subscription
GET /api/subscriptions/me/

Returns current user subscription.

📌 4. Generate Payment Link
POST /api/payments/create-link/

Input:

{
  "subscription_id": 123
}

Logic:

Validate subscription belongs to user
Call payment provider API
Return payment_url

Output:

{
  "payment_url": "https://provider.com/pay/xyz"
}
📌 5. Webhook Endpoint (CRITICAL)
POST /api/payments/webhook/
🔐 WEBHOOK REQUIREMENTS
MUST:
Validate provider signature
Ensure idempotency (no duplicate processing)
Validate:
amount
currency
subscription_id
Webhook Flow:
if payment_success:
    create/update SubscriptionPayment
    mark succeeded=True
    trigger subscription update
❗ IMPORTANT

Never trust webhook blindly.

Must validate:

provider_payment_id uniqueness
signature
amount matches plan price
3. BUSINESS LOGIC RULES
✅ Subscription Activation

Triggered when:

payment.succeeded == True

Then:

is_active = True
status = ACTIVE
last_payment_date updated
ends_at extended
✅ Subscription Renewal

If:

ends_at > now

Then:

ends_at += duration

Else:

ends_at = now + duration
✅ Subscription Expiration

Handled by:

cron job / celery (recommended)
OR
lazy check on access
✅ Only One Active Subscription

Enforced via DB constraint:

UniqueConstraint(user, is_active=True)
4. BACKWARD COMPATIBILITY
Existing endpoints should not break (if used in production)
Provide migration strategy:
map old fields → new ones
clean inconsistent data
5. SECURITY REQUIREMENTS
Webhook signature validation (mandatory)
Prevent duplicate payments
Validate ownership of subscription
Use transactions for payment updates
6. PERFORMANCE
Add indexes (already in model)
Optimize queries:
select_related("plan")
prefetch_related("payments")
7. TESTING REQUIREMENTS
Must cover:
Subscription creation
Payment success flow
Payment duplication
Expired subscription logic
Constraint violation (multiple active subscriptions)
8. FUTURE EXTENSIONS (NOT NOW)
Multi-provider support
Coupons / discounts
Trial subscriptions
Auto-renewal
Grace period
🚀 FINAL RESULT

After refactor, the system must:

✅ Support real payment providers
✅ Be fully webhook-driven
✅ Automatically manage subscription lifecycle
✅ Prevent inconsistent states
✅ Be production-ready and scalable