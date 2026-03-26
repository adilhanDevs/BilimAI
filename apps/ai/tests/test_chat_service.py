from django.test import TestCase, override_settings

from apps.ai.services.chat_service import ChatService


class ChatServiceTests(TestCase):
    @override_settings(OPENAI_API_KEY=None, HF_API_TOKEN=None)
    def test_mock_without_api_key(self):
        text = ChatService.generate_reply("hello", [])
        self.assertIn("mock", text.lower())
        self.assertIn("hello", text)
