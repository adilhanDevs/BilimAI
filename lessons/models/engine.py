import uuid
from django.db import models
from .course import Lesson
from .localization import TranslationGroup


class LessonStepQuerySet(models.QuerySet):
    def with_details(self, lang=None):
        """
        Optimizes fetching LessonStep details by using the StepRegistry 
        to select_related and prefetch_related all registered step types.
        """
        from ..registry import StepRegistry
        from django.db.models import Prefetch
        from .localization import Translation

        select_related = ['lesson', 'prompt_group', 'instruction_group']
        prefetch_related = []
        
        if lang:
            translation_qs = Translation.objects.filter(language_id=lang)
            prefetch_related.extend([
                Prefetch('prompt_group__translations', queryset=translation_qs, to_attr='active_translations'),
                Prefetch('instruction_group__translations', queryset=translation_qs, to_attr='active_translations'),
            ])

        for config in StepRegistry.get_all_configs():
            select_related.append(config.relation_name)

        prefetch_related.extend(StepRegistry.get_optimized_prefetches(lang=lang))
        
        return self.select_related(*select_related).prefetch_related(*prefetch_related)


class LessonStepManager(models.Manager):
    def get_queryset(self):
        return LessonStepQuerySet(self.model, using=self._db)

    def with_details(self, lang=None):
        return self.get_queryset().with_details(lang=lang)


class LessonStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='steps')
    step_type = models.CharField(max_length=50)
    
    prompt_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    instruction_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    prompt = models.TextField(blank=True, null=True, help_text="Fallback instruction or question prompt")
    instruction = models.TextField(blank=True, null=True, help_text="Fallback instructional hint")
    
    xp_reward = models.IntegerField(default=10)
    sort_order = models.IntegerField(default=0)

    objects = LessonStepManager()

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.lesson.title} - Step {self.sort_order} ({self.step_type})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from ..registry import StepRegistry
        if not StepRegistry.get(self.step_type):
            raise ValidationError(f"Unsupported step_type: {self.step_type}")

    @property
    def detail(self):
        from ..registry import StepRegistry
        config = StepRegistry.get(self.step_type)
        if config and config.relation_name:
            return getattr(self, config.relation_name, None)
        return None


class Asset(models.Model):
    ASSET_TYPES = [
        ('audio', 'Audio'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    file = models.FileField(upload_to='assets/%Y/%m/%d/')
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.asset_type}: {self.file.name}"


class ContentUnit(models.Model):
    UNIT_TYPES = [
        ('word', 'Word'),
        ('phrase', 'Phrase'),
        ('sentence', 'Sentence'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    
    text_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    meaning_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    text = models.TextField(blank=True, null=True, help_text="Fallback primary text")
    meaning = models.TextField(blank=True, null=True, help_text="Fallback meaning or translation hint")
    
    primary_audio = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    primary_image = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.text and not self.text_group:
            raise ValidationError("ContentUnit must have either fallback 'text' or a 'text_group'.")

    def __str__(self):
        display = self.text or str(self.id)
        return f"[{self.unit_type}] {display[:30]}"


class StepMultipleChoice(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_multiple_choice')
    allow_multiple = models.BooleanField(default=False, help_text="If true, user can select multiple options (checkbox style)")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'multiple_choice':
            raise ValidationError("Attached step must be of type 'multiple_choice'")


class StepChoice(models.Model):
    step_detail = models.ForeignKey(StepMultipleChoice, on_delete=models.CASCADE, related_name='choices')
    content_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    text = models.CharField(max_length=255, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.text and not self.content_unit:
            raise ValidationError("Choice must have either text or a content_unit.")


class StepFillBlank(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_fill_blank')
    source_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    sentence_template = models.TextField(help_text="The sentence with [[blank]] placeholders")
    acceptable_answers = models.JSONField(help_text="List of correct strings for the blank(s)")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'fill_blank':
            raise ValidationError("Attached step must be of type 'fill_blank'")
        if "[[blank]]" not in self.sentence_template:
            raise ValidationError("Sentence template must include '[[blank]]'")
        if not isinstance(self.acceptable_answers, list) or len(self.acceptable_answers) == 0:
            raise ValidationError("acceptable_answers must be a non-empty list")


class StepMatchPairs(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_match_pairs')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'match_pairs':
            raise ValidationError("Attached step must be of type 'match_pairs'")


class MatchPairItem(models.Model):
    step_detail = models.ForeignKey(StepMatchPairs, on_delete=models.CASCADE, related_name='pairs')
    left_content_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    right_content_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    left_text = models.CharField(max_length=255, blank=True, null=True)
    right_text = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def clean(self):
        from django.core.exceptions import ValidationError
        if not (self.left_content_unit or self.left_text):
            raise ValidationError("Left side must have text or content_unit")
        if not (self.right_content_unit or self.right_text):
            raise ValidationError("Right side must have text or content_unit")


class StepReorderSentence(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_reorder_sentence')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'reorder_sentence':
            raise ValidationError("Attached step must be of type 'reorder_sentence'")


class ReorderToken(models.Model):
    step_detail = models.ForeignKey(StepReorderSentence, on_delete=models.CASCADE, related_name='tokens')
    content_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    text = models.CharField(max_length=255, blank=True, null=True)
    is_distractor = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.text and not self.content_unit:
            raise ValidationError("Token must have text or content_unit")


class StepTypeTranslation(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_type_translation')
    source_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    source_text = models.TextField(blank=True, null=True)
    acceptable_answers = models.JSONField(help_text="List of correct translations")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'type_translation':
            raise ValidationError("Attached step must be of type 'type_translation'")
        if not (self.source_unit or self.source_text):
            raise ValidationError("Must have source_unit or source_text")
        if not isinstance(self.acceptable_answers, list) or len(self.acceptable_answers) == 0:
            raise ValidationError("acceptable_answers must be a non-empty list")


class StepSpeakPhrase(models.Model):
    step = models.OneToOneField(LessonStep, on_delete=models.CASCADE, related_name='detail_speak_phrase')
    target_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    target_text = models.TextField(blank=True, null=True)
    target_text_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reference_audio = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    min_score_required = models.IntegerField(default=70)
    allow_retry = models.BooleanField(default=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.step.step_type != 'speak_phrase':
            raise ValidationError("Attached step must be of type 'speak_phrase'")
        if not (self.target_unit or self.target_text or self.target_text_group):
            raise ValidationError("Must have target phrase (unit, text, or group)")
