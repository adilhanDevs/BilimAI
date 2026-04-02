import uuid
from django.db import models


class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    source_language = models.CharField(max_length=10, help_text="Language of instruction (e.g., 'en')")
    target_language = models.CharField(max_length=10, help_text="Language being learned (e.g., 'tr')")
    title = models.CharField(max_length=255)
    description_ky = models.TextField(blank=True, null=True, help_text="Description in Kyrgyz")
    cefr_min = models.CharField(max_length=10, blank=True, null=True, help_text="Minimum CEFR level (e.g., 'A1')")
    cefr_max = models.CharField(max_length=10, blank=True, null=True, help_text="Maximum CEFR level (e.g., 'B2')")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.title


class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='units')
    slug = models.SlugField()
    title = models.CharField(max_length=255)
    description_ky = models.TextField(blank=True, null=True, help_text="Description in Kyrgyz")
    sort_order = models.IntegerField(default=0)
    cefr_level = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']
        unique_together = ('course', 'slug')

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='categories')
    slug = models.SlugField(unique=True)
    title_ky = models.CharField(max_length=255, help_text="Title in Kyrgyz")
    title_target = models.CharField(max_length=255, help_text="Title in target language")
    description_ky = models.TextField(blank=True, null=True, help_text="Description in Kyrgyz")
    icon = models.TextField(blank=True, null=True, help_text="Icon name or URL")
    difficulty = models.CharField(max_length=50, default='beginner')
    sort_order = models.IntegerField(default=0)
    estimated_minutes = models.IntegerField(default=0)
    vocabulary_count = models.IntegerField(default=0)
    is_premium = models.BooleanField(default=False)
    prerequisite_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='next_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']
        verbose_name_plural = "Categories"

    def __str__(self):
        return str(self.title_ky or "Unnamed Category")


class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='lessons')
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='lessons')
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description_ky = models.TextField(blank=True, null=True, help_text="Description in Kyrgyz")
    level = models.CharField(max_length=10, default='a0')
    difficulty = models.CharField(max_length=50, default='beginner')
    duration_min = models.IntegerField(default=5)
    xp_reward = models.IntegerField(default=10)
    grammar_focus = models.TextField(blank=True, null=True)
    is_premium = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.title


class LessonVocabulary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='vocabulary')
    content_unit = models.ForeignKey('lessons.ContentUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name='vocabulary_references')
    word_or_phrase_target = models.CharField(max_length=255)
    translation_ky = models.CharField(max_length=255)
    transliteration = models.CharField(max_length=255, blank=True, null=True)
    part_of_speech = models.CharField(max_length=50, blank=True, null=True)
    example_target = models.TextField(blank=True, null=True)
    example_ky = models.TextField(blank=True, null=True)
    audio_url = models.URLField(blank=True, null=True)
    difficulty = models.CharField(max_length=50, default='beginner')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']
        verbose_name_plural = "Lesson vocabularies"

    def __str__(self):
        return f"{self.word_or_phrase_target} ({self.lesson.title})"
