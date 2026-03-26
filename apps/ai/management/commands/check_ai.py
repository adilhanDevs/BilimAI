from django.core.management.base import BaseCommand
from django.conf import settings

from apps.ai.services.chat_service import ChatService, ChatServiceError


class Command(BaseCommand):
    help = "Check if AI provider is reachable and configured"

    def handle(self, *args, **options):
        self.stdout.write("Checking AI provider...\n")

        hf_token = getattr(settings, "HF_API_TOKEN", None)
        api_url = getattr(settings, "OPENAI_API_URL", "https://router.huggingface.co/v1/chat/completions")
        model = getattr(settings, "OPENAI_MODEL", "openai/gpt-oss-120b")

        self.stdout.write(f"HF_API_TOKEN exists: {'YES' if hf_token else 'NO'}")
        self.stdout.write(f"API URL: {api_url}")
        self.stdout.write(f"MODEL: {model}\n")

        try:
            reply = ChatService.generate_reply("Reply with exactly one word: OK", [])
            self.stdout.write(self.style.SUCCESS("AI provider works"))
            self.stdout.write(f"Reply: {reply}")
        except ChatServiceError as exc:
            self.stdout.write(self.style.ERROR("AI provider failed"))
            self.stdout.write(f"Error: {exc}")
