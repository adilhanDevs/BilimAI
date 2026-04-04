from django.contrib import admin
from .models.course import Course, Unit, Category, Lesson, LessonVocabulary
from .models.engine import (
    LessonStep, StepMultipleChoice, StepChoice, StepFillBlank, StepMatchPairs,
    MatchPairItem, StepReorderSentence, ReorderToken, StepTypeTranslation,
    StepAnswer, StepSpeakPhrase
)

class StepChoiceInline(admin.TabularInline):
    model = StepChoice
    extra = 1

@admin.register(StepMultipleChoice)
class StepMultipleChoiceAdmin(admin.ModelAdmin):
    list_display = ['step', 'allow_multiple']
    inlines = [StepChoiceInline]

class StepAnswerInline(admin.TabularInline):
    model = StepAnswer
    extra = 1
    fields = ('translation_group', 'text_fallback', 'blank_index', 'is_primary', 'case_sensitive', 'ignore_punctuation', 'sort_order')

@admin.register(StepFillBlank)
class StepFillBlankAdmin(admin.ModelAdmin):
    list_display = ['step', 'sentence_template']
    inlines = [StepAnswerInline]
    readonly_fields = ['acceptable_answers'] # Deprecated

@admin.register(StepTypeTranslation)
class StepTypeTranslationAdmin(admin.ModelAdmin):
    list_display = ['step', 'source_unit']
    inlines = [StepAnswerInline]
    readonly_fields = ['acceptable_answers', 'source_text'] # Deprecated

@admin.register(LessonStep)
class LessonStepAdmin(admin.ModelAdmin):
    list_display = ['id', 'lesson', 'step_type', 'difficulty', 'sort_order']
    list_filter = ['step_type', 'difficulty', 'cefr_level']
    fieldsets = (
        (None, {'fields': ('lesson', 'step_type', 'sort_order', 'xp_reward')}),
        ('Content', {'fields': ('prompt_group', 'instruction_group', 'prompt', 'instruction')}),
        ('Metadata & Pedagogy', {
            'fields': ('difficulty', 'cefr_level', 'is_optional', 'hint_group', 'grammar_note_group'),
            'classes': ('collapse',)
        }),
    )

@admin.register(StepMatchPairs)
class StepMatchPairsAdmin(admin.ModelAdmin):
    pass

@admin.register(StepReorderSentence)
class StepReorderSentenceAdmin(admin.ModelAdmin):
    pass

@admin.register(StepSpeakPhrase)
class StepSpeakPhraseAdmin(admin.ModelAdmin):
    list_display = ['step', 'target_text', 'min_score_required']

admin.site.register(Course)
admin.site.register(Unit)
admin.site.register(Category)
admin.site.register(Lesson)
admin.site.register(LessonVocabulary)
admin.site.register(MatchPairItem)
admin.site.register(ReorderToken)
