# Quickstart

## Prerequisites

- Python 3.11+ (the Dockerfile uses Python 3.12)
- Redis (optional but recommended)
- PostgreSQL (optional; use SQLite for local dev)

## 1) Create environment

```bash
cp .env.example .env
```

Edit `.env`:

- `DEBUG=true/false`
- `DJANGO_SECRET_KEY` (set a real value for production)
- `USE_POSTGRES=true` if you want PostgreSQL
- `REDIS_URL` and `CELERY_BROKER_URL` if you want Redis-backed caching / Celery
- (optional) AI:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`

## 2) Install dependencies and run migrations

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
```

## 3) Create a user (admin)

```bash
python manage.py createsuperuser
```

Superuser creation uses the custom user model:

- `nickname` + `email`
- `password`

## 4) Run the server

```bash
python manage.py runserver
```

Base URL:

- `http://127.0.0.1:8000/api/`

## 5) Run tests

```bash
python manage.py test
```

## Docker (optional)

```bash
docker compose up --build
```

This runs:

- `web` (Django + Gunicorn)
- `db` (PostgreSQL)
- `redis`
- `celery` worker

