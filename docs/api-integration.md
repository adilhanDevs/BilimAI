# API Integration Guide

## Base URL

- Local/dev: `http://127.0.0.1:8000`
- Production: whatever you deploy on

Routes are mounted under:

- `/api/`

## Response envelope

Most responses follow:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

Errors include:

```json
{
  "success": false,
  "data": null,
  "error": { "...": "..." }
}
```

For AI provider failures, `error.detail` is returned (and HTTP 502 is used).

## Authentication (JWT)

Login to get tokens:

- `POST /api/auth/login/`
  - Body: `{ "nickname": "...", "password": "..." }`
  - Response `data` contains `access` and `refresh`

Use the access token for protected endpoints:

`Authorization: Bearer <ACCESS_TOKEN>`

Refresh tokens:

- `POST /api/auth/token/refresh/`

Get current user:

- `GET /api/auth/me/`

## Subscription gating

Premium endpoints (AI + gamification) require an active subscription.

To create/activate a subscription:

- `POST /api/subscriptions/`
  - Body:
    - `plan_type`: `"monthly"` or `"yearly"`
    - `last_payment_date` (optional): ISO-8601 datetime; defaults to server time when omitted

Subscription validity rule:

- monthly: active if `now - last_payment_date` is within 30 days (inclusive)
- yearly: active if within 365 days (inclusive)

## Endpoints

### Auth

1. Register
- `POST /api/auth/register/`
- Body:
  - `nickname` (unique)
  - `email` (unique)
  - `password` (Django-validated)
  - `password2` (must match `password`)
  - `first_name` (optional)
  - `last_name` (optional)

2. Login
- `POST /api/auth/login/`
- Body: `{ "nickname": "...", "password": "..." }`

3. Refresh
- `POST /api/auth/token/refresh/`

4. Me
- `GET /api/auth/me/`

### Subscriptions

- List/create:
  - `GET /api/subscriptions/`
  - `POST /api/subscriptions/`

- Retrieve/update:
  - `GET /api/subscriptions/{id}/`
  - `PUT/PATCH /api/subscriptions/{id}/`

Notes:
- `user` and `is_active` are read-only in the serializer.
- `is_active` is derived from `last_payment_date` via server-side validation.

### Gamification

1. Summary
- `GET /api/gamification/me/`
- Returns current `points`, `level`, `streak`, and reward flags.

2. Daily session
- `POST /api/gamification/session/`
- No body required; returns the updated gamification summary.

3. Activity logs
- `GET /api/gamification/activity/`
- Returns recent activity entries (`DAILY_SESSION`, `STREAK_BONUS`).

### AI Chat

1. Chat
- `POST /api/ai/chat/`
- Body:
  - `message`: string

If `OPENAI_API_KEY` is not set in the server environment, the backend returns a mock reply instead of calling a real LLM.

To use OpenRouter (OpenAI-compatible), set:
- `OPENAI_API_URL=https://openrouter.ai/api/v1/chat/completions`
- `OPENAI_MODEL=openai/gpt-oss-120b` (or another OpenRouter model id)
- `OPENROUTER_API_KEY` (preferred) or `OPENAI_API_KEY` (fallback) with your OpenRouter API key

2. Chat history
- `GET /api/ai/history/`
- Results are paginated using the project pagination settings.

## Example flow (curl)

### 1) Register + Login

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "nickname":"demo",
    "email":"demo@example.com",
    "password":"Str0ngP@ssw0rd",
    "password2":"Str0ngP@ssw0rd",
    "first_name":"Demo",
    "last_name":"User"
  }'

TOKEN_JSON=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"nickname":"demo","password":"Str0ngP@ssw0rd"}')

ACCESS_TOKEN=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d["data"]["access"])' <<<"$TOKEN_JSON")
```

### 2) Create subscription

```bash
curl -s -X POST http://127.0.0.1:8000/api/subscriptions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"plan_type":"monthly"}'
```

### 3) Call AI chat

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"message":"Hello! Give me a short summary of photosynthesis."}'
```

### 4) Record daily session

```bash
curl -s -X POST http://127.0.0.1:8000/api/gamification/session/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{}'
```

