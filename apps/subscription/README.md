# 📚 Subscription & Payment System Documentation

This document explains the architecture, management, and frontend integration of the newly refactored `subscription` app in BilimAI.

---

## 🏗️ Architecture Overview

The system consists of three main entities:
1. **`SubscriptionPlan`**: Defines the pricing plans (e.g., "Monthly Premium", "Annual Mastery") with duration and price.
2. **`Subscription`**: Maps a User to a Plan. A subscription is created as `PENDING` (inactive) until paid. A user can only have **one** active subscription at a time.
3. **`SubscriptionPayment`**: Tracks invoices/payments from the payment provider via Webhook. A successful payment automatically activates or renews the associated `Subscription`.

---

## 🛠️ Backend Management: How to Add New Plans

Because the system is dynamic, you **no longer need to change code** to add a new subscription plan.

1. Go to the **Django Admin Panel** (`/admin/`).
2. Navigate to **Subscriptions > Subscription plans**.
3. Click **Add Subscription Plan** and fill in:
   - **Name**: e.g., Base Monthly
   - **Code**: e.g., `base_1m` (unique identifier)
   - **Duration days**: e.g., `30`
   - **Price**: e.g., `150.00`
   - **Features**: (Optional JSON) e.g., `{"ad_free": true, "ai_tutor": false}`
   - **Is Active**: Checked (visible to users).
4. Save. It will instantly appear in the Frontend API.

---

## 🌐 Frontend API Integration Flow

This is the exact sequence the frontend application should follow to allow a user to buy or renew a subscription:

### Step 1: Fetch Available Plans
When the user visits the "Premium/Shop" screen, fetch the active plans.
```http
GET /api/subscriptions/plans/
```
**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "name": "Base Monthly",
      "code": "base_1m",
      "duration_days": 30,
      "price": "150.00",
      "currency": "KGS"
    }
  ]
}
```

### Step 2: User Chooses a Plan
When the user selects a plan, create a `PENDING` subscription representing their intent to buy.
*(If a user already has a pending subscription for this plan, you can reuse it, but creating a new one is also fine).*
```http
POST /api/subscriptions/
Content-Type: application/json

{
  "plan_id": 1
}
```
**Response (201 Created)**:
```json
{
  "data": {
    "id": 45,
    "status": "pending",
    "is_active": false,
    "plan": { ... }
  }
}
```

### Step 3: Request Payment Link
Ask the backend to generate a payment gateway URL for this transaction.
*(Currently, this returns a mock provider link, but you will replace it with FreedomPay/Stripe etc.)*
```http
POST /api/subscriptions/payments/create-link/
Content-Type: application/json

{
  "subscription_id": 45
}
```
**Response**:
```json
{
  "data": {
    "payment_url": "https://mock-provider.com/pay/45?amount=150.00"
  }
}
```
**Action**: The frontend redirects the user to `payment_url` or opens it in an in-app WebView.

### Step 4: Payment Confirmation (Webhook)
While the user pays on the provider's page, the provider will silently send a Webhook to our backend.
```http
POST /api/subscriptions/payments/webhook/
```
The backend automatically:
- Validates the payment.
- Extends the `ends_at` expiration date dynamically.
- Flags the subscription `is_active = True`.

### Step 5: Check Current User Subscription
When the user returns to the app, verify if the subscription was activated. Polling or fetching on mount is recommended:
```http
GET /api/subscriptions/me/
```
**Response**:
```json
{
  "data": {
    "id": 45,
    "status": "active",
    "is_active": true,
    "starts_at": "2026-03-26T12:00:00Z",
    "ends_at": "2026-04-25T12:00:00Z",
    "plan": { ... }
  }
}
```
*(If `data` is empty, the user has no subscriptions at all).*

---

## 🔒 Webhook Integration Notes (For Backend Devs)

The current webhook at `POST /api/subscriptions/payments/webhook/` heavily relies on idempotency to prevent duplicate payments.

If you integrate a real payment provider (e.g., Stripe or PayBox):
1. **Update `create_link` (views.py)**: Call the provider's SDK to generate the real checkout URL.
2. **Update `webhook` (views.py)**: 
   - Add cryptographic signature verification before moving on to processing.
   - Map the provider's payload structure into the standard internal payload structure handled by `SubscriptionService.process_webhook_payment(data)`.
