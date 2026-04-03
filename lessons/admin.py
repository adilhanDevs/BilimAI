from django.contrib import admin
from django.utils.html import format_html
import logging
import traceback
logger = logging.getLogger(__name__)
from django.urls import reverse
from .models.course import Course, Unit, Category, Lesson, LessonVocabulary
from .models.engine import (
    LessonStep, Asset, ContentUnit, 
    StepMultipleChoice, StepChoice, StepFillBlank,
    StepMatchPairs, MatchPairItem, StepReorderSentence,
    ReorderToken, StepTypeTranslation, StepSpeakPhrase
)
from .models.localization import Language, TranslationGroup, Translation
from .models.progress import (
    CourseEnrollment, UserLessonProgress, UserCategoryProgress,
    ReviewItem, UserSkillProgress
)

# --- Localization Admin ---

class TranslationInline(admin.TabularInline):
    model = Translation
    extra = 1

@admin.register(TranslationGroup)
class TranslationGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'context_note', 'get_translations_summary')
    inlines = [TranslationInline]
    search_fields = ('id', 'context_note', 'translations__text')

    def get_translations_summary(self, obj):
        trans = obj.translations.all()[:3]
        return ", ".join([f"{t.language_id}: {t.text[:20]}" for t in trans])
    get_translations_summary.short_description = "Translations"

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')

# --- Engine Core Admin ---

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset_type', 'file', 'created_at')
    list_filter = ('asset_type', 'created_at')
    search_fields = ('file', 'metadata')

@admin.register(ContentUnit)
class ContentUnitAdmin(admin.ModelAdmin):
    list_display = ('id', 'unit_type', 'text', 'get_kyrgyz_text', 'created_at')
    list_filter = ('unit_type', 'created_at')
    search_fields = ('text', 'meaning', 'text_group__translations__text')
    autocomplete_fields = ('text_group', 'meaning_group', 'primary_audio', 'primary_image')

    def get_kyrgyz_text(self, obj):
        if obj.text_group:
            ky = obj.text_group.translations.filter(language_id='ky').first()
            return ky.text if ky else "-"
        return "-"
    get_kyrgyz_text.short_description = "Kyrgyz Text"

# --- Step Detail Inlines ---

class StepMultipleChoiceInline(admin.StackedInline):
    model = StepMultipleChoice
    can_delete = False
    verbose_name_plural = "Detail: Multiple Choice"

class StepFillBlankInline(admin.StackedInline):
    model = StepFillBlank
    can_delete = False
    autocomplete_fields = ('source_unit',)
    verbose_name_plural = "Detail: Fill Blank"

class StepMatchPairsInline(admin.StackedInline):
    model = StepMatchPairs
    can_delete = False
    verbose_name_plural = "Detail: Match Pairs"

class StepReorderSentenceInline(admin.StackedInline):
    model = StepReorderSentence
    can_delete = False
    verbose_name_plural = "Detail: Reorder Sentence"

class StepTypeTranslationInline(admin.StackedInline):
    model = StepTypeTranslation
    can_delete = False
    autocomplete_fields = ('source_unit',)
    verbose_name_plural = "Detail: Type Translation"

class StepSpeakPhraseInline(admin.StackedInline):
    model = StepSpeakPhrase
    can_delete = False
    autocomplete_fields = ('target_unit', 'target_text_group', 'reference_audio')
    verbose_name_plural = "Detail: Speak Phrase"

# --- Lesson Step Admin ---

@admin.register(LessonStep)
class LessonStepAdmin(admin.ModelAdmin):
    list_display = ('sort_order', 'step_type', 'lesson', 'xp_reward', 'get_detail_link')
    list_filter = ('step_type', 'lesson__category', 'lesson__unit')
    search_fields = ('lesson__title', 'prompt', 'instruction')
    autocomplete_fields = ('lesson', 'prompt_group', 'instruction_group')
    ordering = ('lesson', 'sort_order')
    
    inlines = [
        StepMultipleChoiceInline,
        StepFillBlankInline,
        StepMatchPairsInline,
        StepReorderSentenceInline,
        StepTypeTranslationInline,
        StepSpeakPhraseInline
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj: # editing an existing object
            return ('step_type',) + self.readonly_fields
        return self.readonly_fields

    def get_detail_link(self, obj):
        detail = obj.detail
        if not detail:
            return "No detail created"
        
        # Link to specific detail model admin if we want, but inlines are already here
        return "Manage below"
    get_detail_link.short_description = "Status"

# --- Nested Inlines for Details (Advanced) ---

class StepChoiceInline(admin.TabularInline):
    model = StepChoice
    extra = 3
    autocomplete_fields = ['content_unit']
    fields = ('content_unit', 'get_kyrgyz_text', 'text', 'is_correct', 'sort_order')
    readonly_fields = ('get_kyrgyz_text',)

    def get_kyrgyz_text(self, obj):
        if obj.content_unit and obj.content_unit.text_group:
            ky = obj.content_unit.text_group.translations.filter(language_id='ky').first()
            return ky.text if ky else "-"
        return "-"
    get_kyrgyz_text.short_description = "Kyrgyz"

@admin.register(StepMultipleChoice)
class StepMultipleChoiceAdmin(admin.ModelAdmin):
    inlines = [StepChoiceInline]
    search_fields = ('step__lesson__title',)

class MatchPairItemInline(admin.TabularInline):
    model = MatchPairItem
    extra = 3
    autocomplete_fields = ['left_content_unit', 'right_content_unit']
    fields = ('left_content_unit', 'get_left_ky', 'right_content_unit', 'get_right_ky', 'left_text', 'right_text', 'sort_order')
    readonly_fields = ('get_left_ky', 'get_right_ky')

    def get_left_ky(self, obj):
        if obj.left_content_unit and obj.left_content_unit.text_group:
            ky = obj.left_content_unit.text_group.translations.filter(language_id='ky').first()
            return ky.text if ky else "-"
        return "-"
    
    def get_right_ky(self, obj):
        if obj.right_content_unit and obj.right_content_unit.text_group:
            ky = obj.right_content_unit.text_group.translations.filter(language_id='ky').first()
            return ky.text if ky else "-"
        return "-"

@admin.register(StepMatchPairs)
class StepMatchPairsAdmin(admin.ModelAdmin):
    inlines = [MatchPairItemInline]
    search_fields = ('step__lesson__title',)

class ReorderTokenInline(admin.TabularInline):
    model = ReorderToken
    extra = 3
    autocomplete_fields = ['content_unit']
    fields = ('content_unit', 'get_kyrgyz_text', 'text', 'is_distractor', 'sort_order')
    readonly_fields = ('get_kyrgyz_text',)

    def get_kyrgyz_text(self, obj):
        if obj.content_unit and obj.content_unit.text_group:
            ky = obj.content_unit.text_group.translations.filter(language_id='ky').first()
            return ky.text if ky else "-"
        return "-"

@admin.register(StepReorderSentence)
class StepReorderSentenceAdmin(admin.ModelAdmin):
    inlines = [ReorderTokenInline]
    search_fields = ('step__lesson__title',)

# --- Lesson & Course Admin ---

class LessonStepInline(admin.TabularInline):
    model = LessonStep
    fields = ('sort_order', 'step_type', 'xp_reward')
    extra = 1
    show_change_link = True

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'unit', 'level', 'difficulty', 'sort_order', 'is_published')
    list_filter = ('category', 'unit', 'level', 'difficulty', 'is_premium', 'is_published')
    search_fields = ('title', 'slug', 'subtitle')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LessonStepInline]

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'source_language', 'target_language', 'is_published')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'sort_order')
    list_filter = ('course',)
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title_ky', 'course', 'difficulty', 'sort_order')
    list_filter = ('course', 'difficulty')
    search_fields = ('title_ky', 'slug')
    prepopulated_fields = {'slug': ('title_ky',)}

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context=extra_context)
        except Exception as e:
            logger.error(f"\n====================================\nCRITICAL CATEGORY ADMIN ERROR:\n{e}\n{traceback.format_exc()}\n====================================\n".replace('\n', ' --NEXT_LINE-- '))
            raise

# --- Progress Admin ---

@admin.register(UserLessonProgress)
class UserLessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'status', 'best_score', 'last_activity_at')
    list_filter = ('status', 'lesson__category')
    search_fields = ('user__username', 'user__email', 'lesson__title')
    readonly_fields = ('id', 'last_activity_at')

@admin.register(ReviewItem)
class ReviewItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_type', 'target_text', 'due_at', 'is_completed')
    list_filter = ('item_type', 'is_completed')
    search_fields = ('user__username', 'target_text')

# Register remaining basic models
admin.site.register(CourseEnrollment)
admin.site.register(UserCategoryProgress)
admin.site.register(UserSkillProgress)
admin.site.register(LessonVocabulary)
