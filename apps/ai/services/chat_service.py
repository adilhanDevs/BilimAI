from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
MAX_RETRIES = 3
RETRY_BACKOFF = 0.75


class ChatServiceError(Exception):
    """Raised when the external model provider fails after retries."""


class ChatService:
    @staticmethod
    def _build_messages(user_text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": "You are BilimAI — a friendly, strict-but-supportive Kyrgyz language teacher. UI language: Russian. Teach step-by-step (assume A1 if not specified). Be interactive: ask the student to answer, then correct. Correct format: 1) student's sentence, 2) corrected version, 3) brief rule, 4) 2–3 examples, 5) 1 short exercise. Use Kyrgyz (Cyrillic) by default; Latin only if requested. Keep replies structured: Тема / Правило / Примеры / Практика / Мини-домашка."},
        ]
        for row in history:
            role = row.get("role")
            content = row.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        return messages

    @classmethod
    def _mock_reply(cls, user_text: str) -> str:
        # Clarify which env var is expected for the live provider. The
        # implementation actually checks HF_API_TOKEN, so mention that here.
        return (
            "[BilimAI mock — set HF_API_TOKEN for live LLM] "
            f"I heard: {user_text[:500]}{'…' if len(user_text) > 500 else ''}"
        )

    @classmethod
    def generate_reply(cls, user_text: str, history: list[dict[str, str]]) -> str:
        messages = cls._build_messages(user_text, history)
        # Prefer an explicit, non-empty OPENAI_API_KEY. If it's missing or
        # empty, fall back to HF_API_TOKEN (if present). This keeps runtime
        # behavior using available tokens while treating empty strings as
        # 'not configured'.
        api_key = getattr(settings, "HF_API_TOKEN", None)
  
        if not api_key:
            return cls._mock_reply(user_text)

        # Perform the external call with the resolved api_key.
        messages = cls._build_messages(user_text, history)
        return cls._call_openai_with_key(messages, api_key)

    @classmethod
    def _call_openai_with_key(cls, messages: list[dict[str, str]], api_key: str) -> str:
        url = getattr(settings, "OPENAI_API_URL", "https://router.huggingface.co/v1/chat/completions")
        model = getattr(settings, "OPENAI_MODEL", "openai/gpt-oss-120b")

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    body = resp.json()
                choices = body.get("choices") or []
                if not choices:
                    raise ChatServiceError("Empty choices from provider")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if not content:
                    raise ChatServiceError("Empty content from provider")
                return str(content).strip()
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_exc = exc
                logger.warning("OpenAI request failed attempt=%s error=%s", attempt, exc)
                time.sleep(RETRY_BACKOFF * attempt)

        raise ChatServiceError(str(last_exc) if last_exc else "Unknown error")
    
