import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q
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

        select_related = ['lesson', 'prompt_group', 'instruction_group', 'hint_group', 'grammar_note_group']
        prefetch_related = []
        
        if lang:
            translation_qs = Translation.objects.filter(language_id=lang)
            prefetch_related.extend([
                Prefetch('prompt_group__translations', queryset=translation_qs, to_attr='active_translations'),
                Prefetch('instruction_group__translations', queryset=translation_qs, to_attr='active_translations'),
                Prefetch('hint_group__translations', queryset=translation_qs, to_attr='active_translations'),
                Prefetch('grammar_note_group__translations', queryset=translation_qs, to_attr='active_translations'),
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

    # NEW METADATA FIELDS (Phase 1)
    difficulty = models.PositiveSmallIntegerField(
        default=1, 
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Difficulty level 1-10"
    )
    cefr_level = models.CharField(max_length=2, blank=True, null=True, choices=[
        ('A1', 'A1'), ('A2', 'A2'), ('B1', 'B1'), ('B2', 'B2'), ('C1', 'C1'), ('C2', 'C2')
    ])
    hint_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    grammar_note_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_optional = models.BooleanField(default=False, help_text="If true, mistakes do not deplete hearts")

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
    
    # NEW FEEDBACK FIELD (Phase 1)
    explanation_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

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
    
    # TODO: Phase 3 removal - Deprecated legacy JSON field
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
    
    # NEW SOURCE FIELD (Phase 1)
    source_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # TODO: Phase 3 removal - Deprecated legacy fields
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


class StepAnswer(models.Model):
    """
    NEW MODEL (Phase 2): Relational answers for FillBlank and TypeTranslation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Links to detail tables
    step_fill_blank = models.ForeignKey(StepFillBlank, on_delete=models.CASCADE, null=True, blank=True, related_name='relational_answers')
    step_type_translation = models.ForeignKey(StepTypeTranslation, on_delete=models.CASCADE, null=True, blank=True, related_name='relational_answers')
    
    # Content
    translation_group = models.ForeignKey(TranslationGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    text_fallback = models.CharField(max_length=255, blank=True, null=True)
    
    # Evaluation Logic
    blank_index = models.PositiveIntegerField(default=0, help_text="Index of the blank in the template (0 for translation)")
    is_primary = models.BooleanField(default=False, help_text="The main answer to show in feedback")
    case_sensitive = models.BooleanField(default=False)
    ignore_punctuation = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # FUTURE-PROOFING: Support for semantic evaluation
    answer_embedding = models.JSONField(blank=True, null=True, help_text="Future: Store vector embeddings for AI semantic matching")

    class Meta:
        ordering = ['blank_index', 'sort_order', '-is_primary']
        indexes = [
            # Optimized indexes for evaluator lookups
            models.Index(fields=['step_fill_blank', 'blank_index', 'is_primary']),
            models.Index(fields=['step_type_translation', 'blank_index', 'is_primary']),
            models.Index(fields=['translation_group']),
        ]
        constraints = [
            # Mutual exclusivity constraints
            models.CheckConstraint(
                check=(
                    Q(step_fill_blank__isnull=False, step_type_translation__isnull=True) |
                    Q(step_fill_blank__isnull=True, step_type_translation__isnull=False)
                ),
                name='stepanswer_exclusive_step_fk'
            ),
            models.CheckConstraint(
                check=(
                    Q(translation_group__isnull=False, text_fallback__isnull=True) |
                    Q(translation_group__isnull=True, text_fallback__isnull=False) |
                    Q(translation_group__isnull=False, text_fallback__isnull=False)
                ),
                name='stepanswer_content_present'
            ),
            # Partial unique indexes for data integrity (1 primary per blank max)
            models.UniqueConstraint(
                fields=['step_fill_blank', 'blank_index'],
                condition=Q(is_primary=True, step_fill_blank__isnull=False),
                name='unique_primary_fill_blank'
            ),
            models.UniqueConstraint(
                fields=['step_type_translation', 'blank_index'],
                condition=Q(is_primary=True, step_type_translation__isnull=False),
                name='unique_primary_type_translation'
            )
        ]

    def clean(self):
        if not self.step_fill_blank and not self.step_type_translation:
            raise ValidationError("Answer must be linked to a StepFillBlank or StepTypeTranslation.")
        if self.step_fill_blank and self.step_type_translation:
            raise ValidationError("Answer cannot be linked to both FillBlank and TypeTranslation.")
        
        has_trans = bool(self.translation_group)
        has_text = bool(self.text_fallback and self.text_fallback.strip())
        
        if has_trans and has_text:
            raise ValidationError("Answer cannot have both translation_group and text_fallback.")
        if not has_trans and not has_text:
            raise ValidationError("Answer must have either a translation_group or text_fallback.")

    def __str__(self):
        source = "FillBlank" if self.step_fill_blank else "TypeTranslation"
        content = self.text_fallback or f"TG:{self.translation_group_id}"
        return f"[{source}] Blank {self.blank_index}: {content} ({'Primary' if self.is_primary else 'Alt'})"


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
