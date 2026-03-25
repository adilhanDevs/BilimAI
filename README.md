# BilimAI Backend (Django + DRF)

BilimAI is a Django REST backend providing:

- JWT authentication (access + refresh tokens)
- Subscription management (monthly/yearly; active-window validation)
- Gamification (points, level, streak; activity logs)
- AI chat + chat history (LLM provider via OpenAI-compatible HTTP, with a mock mode when no API key is set)

API responses use a consistent envelope:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

When you need to pass an auth token, use:

`Authorization: Bearer <ACCESS_TOKEN>`

## Quickstart

See [`docs/quickstart.md`](docs/quickstart.md).

## API integration

See [`docs/api-integration.md`](docs/api-integration.md).

