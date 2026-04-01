import uuid
from django.db import models


class Language(models.Model):
    code = models.CharField(max_length=10, primary_key=True, help_text="ISO language code (e.g., 'en', 'ky', 'ru')")
    name = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.code})"


class TranslationGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context_note = models.CharField(max_length=255, blank=True, null=True, help_text="Context for translators")

    def __str__(self):
        return f"Group {self.id}"


class Translation(models.Model):
    group = models.ForeignKey(TranslationGroup, on_delete=models.CASCADE, related_name='translations')
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='translations')
    text = models.TextField()

    class Meta:
        unique_together = ('group', 'language')

    def __str__(self):
        return f"{self.language_id}: {self.text[:30]}"
