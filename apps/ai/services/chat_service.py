from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
import os
from dotenv import load_dotenv
from django.conf import settings

logger = logging.getLogger(__name__)

# Tunable defaults
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
MAX_RETRIES = 3
RETRY_BACKOFF = 0.75


class ChatServiceError(Exception):
    """Raised when the external model provider fails after retries."""


class ChatService:
    SYSTEM_PROMPT = "You are BilimAI, a concise helpful assistant."

    @staticmethod
    def _build_messages(user_text: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": ChatService.SYSTEM_PROMPT},
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

    @staticmethod
    def _extract_text_from_response(body: Dict[str, Any]) -> Optional[str]:
        """Handle common response shapes from OpenAI-compatible routers and HF.

        Expected shapes (non-streaming):
        - { choices: [{ message: { content: "..." } }] }
        - { choices: [{ text: "..." }] }
        - { output: "..." } or { output_text: "..." }
        """
        # choices with message.content (OpenAI / HF router)
        choices = body.get("choices")
        if isinstance(choices, list) and len(choices) > 0:
            first = choices[0]
            # message.content could be a string
            message = first.get("message") if isinstance(first, dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                # sometimes content may be a dict/list — try to stringify
                if content:
                    return str(content)

            # fallback to choices[0].text
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

        # other top-level keys
        for key in ("output", "output_text", "result", "text"):
            v = body.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

        return None

    @classmethod
    def generate_reply(cls, user_text: str, history: List[Dict[str, str]]) -> str:
        """Generate a single assistant reply string.

        Behavior (source of truth = frontend):
        - The frontend sends POST /api/ai/chat/ with JSON { message }
        - The backend must call an OpenAI-compatible router (default HF router)
          with a JSON payload { model, messages, temperature }
        - No streaming is used — backend should return the full assistant text.
        """
        # Build messages once
        messages = cls._build_messages(user_text, history)

        # Load .env if present, allow environment to override Django settings
        load_dotenv()

        # Preferred token precedence:
        # 1) OPENROUTER_API_KEY (OpenRouter)
        # 2) OPENAI_API_KEY (OpenAI-compatible key)
        # 3) HF_API_TOKEN (Hugging Face)
        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("HF_API_TOKEN")
        )
        if not api_key:
            # Fall back to Django settings (may be empty string)
            api_key = (
                getattr(settings, "OPENROUTER_API_KEY", None)
                or getattr(settings, "OPENAI_API_KEY", None)
                or getattr(settings, "HF_API_TOKEN", None)
            )

        if not api_key:
            # Don't mock in production; but keep a clear, helpful local message.
            # Tests rely on a mock reply when no key is configured.
            logger.info("No AI API key configured; returning local mock reply")
            return (
                "[BilimAI mock — set OPENAI_API_KEY or HF_API_TOKEN for live LLM] "
                f"I heard: {user_text[:500]}{'…' if len(user_text) > 500 else ''}"
            )

        return cls._call_provider_with_key(messages, api_key)

    @classmethod
    def _call_provider_with_key(cls, messages: List[Dict[str, str]], api_key: str) -> str:
        # Resolve API URL preference: if OPENROUTER_API_KEY is used prefer OPENROUTER_API_URL,
        # then OPENAI_API_URL, then HF router as a last fallback.
        env_openrouter_key = os.getenv("OPENROUTER_API_KEY") or getattr(
            settings, "OPENROUTER_API_KEY", None
        )
        url = None
        if env_openrouter_key:
            url = os.getenv("OPENROUTER_API_URL") or getattr(settings, "OPENROUTER_API_URL", None)
            # OpenRouter official URL as sensible default
            if not url:
                url = "https://openrouter.ai/api/v1/chat/completions"
        else:
            url = (
                os.getenv("OPENAI_API_URL")
                or getattr(settings, "OPENAI_API_URL", None)
                or "https://router.huggingface.co/v1/chat/completions"
            )
        model = os.getenv("OPENAI_MODEL") or getattr(
            settings, "OPENAI_MODEL", "openai/gpt-oss-120b"
        )

        payload: Dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.3}

        # Build headers. OpenRouter docs recommend optional HTTP-Referer and X-OpenRouter-Title
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        # Optional referer/title for OpenRouter ranking/analytics — allow configuring via env/settings
        referer = os.getenv("OPENROUTER_REFERER") or getattr(settings, "OPENROUTER_REFERER", None)
        title = os.getenv("OPENROUTER_TITLE") or getattr(settings, "OPENROUTER_TITLE", None)
        if referer:
            # some examples use 'HTTP-Referer', others use standard 'Referer'
            headers["HTTP-Referer"] = referer
            headers["Referer"] = referer
        if title:
            headers["X-OpenRouter-Title"] = title
        # Content-Type will be set by httpx when using json=

        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    # If non-2xx, include response body in logs/error to help debugging (e.g., 401 Unauthorized)
                    if resp.status_code >= 400:
                        text = None
                        try:
                            text = resp.text
                        except Exception:
                            text = "<unable to read response body>"
                        raise ChatServiceError(f"Provider returned status={resp.status_code} body={text}")
                    try:
                        body = resp.json()
                    except ValueError:
                        raise ChatServiceError("Provider returned invalid JSON")

                text = cls._extract_text_from_response(body)
                if not text:
                    # Include body snippet in logs for debugging
                    logger.warning("Empty assistant text from provider, body=%s", body)
                    raise ChatServiceError("Empty content from provider")

                return text

            except (httpx.HTTPError, ChatServiceError) as exc:
                last_exc = exc
                logger.warning(
                    "AI provider request failed attempt=%s url=%s error=%s",
                    attempt,
                    url,
                    exc,
                )
                # Backoff before retrying
                time.sleep(RETRY_BACKOFF * attempt)

        # All retries exhausted
        raise ChatServiceError(str(last_exc) if last_exc else "Unknown error")
    
