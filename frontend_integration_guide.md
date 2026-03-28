# Chat Endpoint Integration Guide

## Overview
The chat endpoint `/api/ai/chat/` has been refactored to support daily usage limits based on the user's subscription status. Guest (anonymous) users are now also supported, though they do not have persistent chat histories.

## Key Changes
1. **Endpoint Permissions**: The `/api/ai/chat/` endpoint is now completely open (`AllowAny`). The previous hard requirement for an active subscription (`HasActiveSubscription`) has been replaced by a daily rate-limit system.
2. **Limit Tiers**:
   - Guests (Anonymous): 5 per day  (default, configurable via `CHAT_LIMIT_GUEST`)
   - Free Authenticated Users: 10 per day (default, configurable via `CHAT_LIMIT_FREE_AUTH`)
   - Subscribed Users: 100 per day (default, configurable via `CHAT_LIMIT_SUBSCRIBED`)
3. **Atomic Tracking**: Usage is tracked using `DailyChatUsage` safely and atomically.
4. **Limits in Response**: Every response (both success and failure) correctly indicates the usage limit.

## How to Connect the Frontend

### Authenticated Users
Requests for authenticated users should include the standard `Authorization: Bearer <token>` header. The backend will automatically infer their limit tier and accurately increment their daily allowance.

### Guest (Unauthenticated) Users
For users not logged in, the backend requires a unique identifier to trace limits properly.
1. The frontend should generate a random string, UUID, or uniquely identifiable hash per browser session.
2. Store this string within `localStorage` (e.g. `guestChatId`).
3. Set this identifier into the HTTP headers as **`X-Guest-Id`** whenever polling the endpoint.

Example for Guest Users:
```javascript
let guestId = localStorage.getItem("guestChatId");
if (!guestId) {
    guestId = crypto.randomUUID();
    localStorage.setItem("guestChatId", guestId);
}

fetch("/api/ai/chat/", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "X-Guest-Id": guestId  // Crucial for guest tracking
    },
    body: JSON.stringify({ message: "Hello AI!" })
});
```
*Note: The backend has fallbacks to use `HTTP_X_FORWARDED_FOR` and `REMOTE_ADDR`, but passing `X-Guest-Id` intentionally prevents collisions from NAT network routers.*

### Response Format Updates

#### Success (HTTP 201 Created)
In addition to the standard response fields, you will now receive three explicit integers under `data`:
```json
{
  "success": true,
  "data": {
    "id": 123,
    "session_id": 45,
    "message": "Hello AI!",
    "response": "Hello, human!",
    "created_at": "2026-03-28T10:00:00Z",
    "limit": 100,
    "used": 4,
    "remaining": 96
  },
  "error": null
}
```
*(For anonymous guests, `id` and `session_id` will explicitly be `null` since chat DB persistence is bypassed).*

#### Rate Limit Exceeded (HTTP 429 Too Many Requests)
When a user hits their daily limit, the server will block processing and throw an HTTP 429 instead of 201 or 502. 
You can proactively lock the UI if `remaining === 0`.
```json
{
  "success": false,
  "data": {
    "allowed": false,
    "limit": 5,
    "used": 5,
    "remaining": 0
  },
  "error": {
    "detail": "Daily chat limit exceeded."
  }
}
```

## Considerations
- Make sure to update your application code to handle HTTP 429 appropriately by disabling the chat input visually when limits are met.
- The limit counters reset automatically exactly at midnight (`timezone.localdate()`). No cronjob setups are required on the server side.
