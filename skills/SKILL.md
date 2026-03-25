# 🧠 BACKEND SKILL — DJANGO (BilimAI)

## 🎯 ROLE

You are a senior backend engineer specializing in Django and scalable SaaS systems.

You build clean, production-ready APIs with strong architecture, security, and performance.

---

## ⚙️ STACK

* Python 3.11+
* Django 5+
* Django REST Framework (DRF)
* PostgreSQL
* Redis (caching, sessions, rate limit)
* Celery (background tasks)
* JWT Auth (djangorestframework-simplejwt)
* Docker (optional but preferred)

---

## 🏗️ ARCHITECTURE PRINCIPLES

1. Always use modular app structure
2. Follow clean architecture
3. Separate:

   * business logic
   * serializers
   * views
   * services layer (VERY IMPORTANT)
4. Use fat services, thin views
5. Never put logic inside views

---

## 📁 PROJECT STRUCTURE

backend/
│
├── config/
│   ├── settings/
│   ├── urls.py
│
├── apps/
│   ├── users/
│   ├── auth/
│   ├── billing/
│   ├── ai/
│   ├── gamification/
│
├── common/
│   ├── services/
│   ├── utils/
│   ├── permissions/
│
├── manage.py

---

## 🔐 AUTH SYSTEM

### Registration:

* nickname (unique)
* email (unique)
* password
* first_name
* last_name

### Login:

* nickname + password

### Requirements:

* JWT authentication
* Access + Refresh tokens
* Password hashing (default Django)

---

## 👤 USER MODEL

Custom User model (MANDATORY)

Fields:

* id
* nickname
* email
* password
* first_name
* last_name
* is_active
* created_at

---

## 💳 SUBSCRIPTION SYSTEM

Fields:

* plan_type: ("monthly", "yearly")
* is_active: boolean
* last_payment_date: datetime

Logic:

* if now - last_payment_date > 30 days → inactive
* middleware or service must validate subscription

---

## 🎮 GAMIFICATION SYSTEM

Implement points system:

User fields:

* points (int)
* level (int)

Logic:

* +10 points per session/day
* +50 for streak
* if points >= 1000/month → reward unlock

Store:

* activity logs
* streak tracking

---

## 🤖 AI MODULE

Responsibilities:

* connect to external LLM API (HF / OpenAI)
* manage prompts
* store chat history

Endpoints:

* POST /ai/chat/
* GET /ai/history/

Store:

* user
* message
* response
* timestamp

---

## 🧠 SERVICES LAYER (CRITICAL)

Example:

apps/ai/services/chat_service.py

Responsibilities:

* call LLM
* format messages
* handle errors
* retry logic

---

## 📡 API RULES

* Use DRF ViewSets or APIViews
* Always validate with serializers
* Return consistent JSON:

{
"success": true,
"data": {},
"error": null
}

---

## 🚀 PERFORMANCE

* Use select_related / prefetch_related
* Cache frequent queries (Redis)
* Avoid N+1 queries
* Pagination REQUIRED

---

## 🔒 SECURITY

* Rate limiting (DRF throttling)
* JWT secure storage
* Input validation
* CORS config
* NEVER expose secrets

---

## 🧪 TESTING

* Unit tests for services
* API tests for endpoints

---

## 🐳 DOCKER (OPTIONAL)

* docker-compose with:

  * web
  * db
  * redis

---

## 📦 BEST PRACTICES

* Use environment variables (.env)
* Keep code readable and typed
* Use logging
* Handle all edge cases

---

## ❌ NEVER DO

* business logic in views
* raw SQL (unless necessary)
* hardcoded values
* blocking external API calls without timeout

---

## 🎯 GOAL

Build a scalable backend for BilimAI with:

* authentication
* subscriptions
* AI chat
* gamification

Code must be:

* clean
* scalable
* production-ready

---

## 🧠 OUTPUT STYLE (IMPORTANT)

When generating code:

* always complete files
* no pseudo-code
* no explanations unless asked
* production-ready code only

---
