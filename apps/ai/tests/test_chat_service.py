from django.test import TestCase, override_settings

from unittest.mock import patch
from apps.ai.services.chat_service import ChatService


class ChatServiceTests(TestCase):
    @override_settings(OPENAI_API_KEY=None, HF_API_TOKEN=None, OPENROUTER_API_KEY=None)
    @patch.dict('os.environ', {'OPENAI_API_KEY': '', 'HF_API_TOKEN': '', 'OPENROUTER_API_KEY': ''})
    def test_mock_without_api_key(self):
        text = ChatService.generate_reply("hello", [])
        self.assertIn("mock", text.lower())
        self.assertIn("hello", text)
