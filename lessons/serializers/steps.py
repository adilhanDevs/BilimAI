from rest_framework import serializers
from .base import ContentUnitSerializer, AssetSerializer
from ..models.engine import (
    LessonStep, StepMultipleChoice, StepChoice, StepFillBlank, StepMatchPairs,
    MatchPairItem, StepReorderSentence, ReorderToken, StepTypeTranslation,
    StepSpeakPhrase
)
from ..utils.cache import get_cached_translation

class StepChoiceSerializer(serializers.ModelSerializer):
    content_unit = ContentUnitSerializer(read_only=True)
    text = serializers.SerializerMethodField()
    explanation = serializers.SerializerMethodField()

    class Meta:
        model = StepChoice
        fields = ['id', 'text', 'sort_order', 'content_unit', 'explanation']

    def get_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.content_unit:
            return get_cached_translation(obj.content_unit.text_group, lang) or obj.content_unit.text
        return obj.text

    def get_explanation(self, obj):
        lang = self.context.get('lang', 'en')
        return get_cached_translation(obj.explanation_group, lang) if obj.explanation_group else None


class MultipleChoiceDetailSerializer(serializers.ModelSerializer):
    choices = StepChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = StepMultipleChoice
        fields = ['choices']


class FillBlankDetailSerializer(serializers.ModelSerializer):
    source_unit = ContentUnitSerializer(read_only=True)
    answers = serializers.SerializerMethodField()

    class Meta:
        model = StepFillBlank
        fields = ['sentence_template', 'source_unit', 'answers']

    def get_answers(self, obj):
        lang = self.context.get('lang', 'en')
        # Optimized prefetch access
        rel_answers = list(obj.relational_answers.all())
        
        if rel_answers:
            result = []
            # Group by blank_index
            grouped = {}
            for ans in rel_answers:
                if ans.is_primary:
                    text = get_cached_translation(ans.translation_group, lang) if ans.translation_group else ans.text_fallback
                    if text:
                        grouped.setdefault(ans.blank_index, []).append(text)
            
            # Ensure we cover all blanks in order
            if grouped:
                max_idx = max(grouped.keys())
                for i in range(max_idx + 1):
                    opts = grouped.get(i, [""])
                    result.append(opts[0] if len(opts) == 1 else opts)
            return result
            
        return obj.acceptable_answers


class MatchPairItemSerializer(serializers.ModelSerializer):
    left_content_unit = ContentUnitSerializer(read_only=True)
    right_content_unit = ContentUnitSerializer(read_only=True)
    left_text = serializers.SerializerMethodField()
    right_text = serializers.SerializerMethodField()

    class Meta:
        model = MatchPairItem
        fields = ['id', 'left_text', 'right_text', 'left_content_unit', 'right_content_unit', 'sort_order']

    def get_left_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.left_content_unit:
            return get_cached_translation(obj.left_content_unit.text_group, lang) or obj.left_content_unit.text
        return obj.left_text

    def get_right_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.right_content_unit:
            return get_cached_translation(obj.right_content_unit.text_group, lang) or obj.right_content_unit.text
        return obj.right_text


class MatchPairsDetailSerializer(serializers.ModelSerializer):
    pairs = MatchPairItemSerializer(many=True, read_only=True)

    class Meta:
        model = StepMatchPairs
        fields = ['pairs']


class ReorderTokenSerializer(serializers.ModelSerializer):
    content_unit = ContentUnitSerializer(read_only=True)
    text = serializers.SerializerMethodField()

    class Meta:
        model = ReorderToken
        fields = ['id', 'text', 'is_distractor', 'content_unit', 'sort_order']

    def get_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.content_unit:
            return get_cached_translation(obj.content_unit.text_group, lang) or obj.content_unit.text
        return obj.text


class ReorderSentenceDetailSerializer(serializers.ModelSerializer):
    tokens = ReorderTokenSerializer(many=True, read_only=True)

    class Meta:
        model = StepReorderSentence
        fields = ['tokens']


class TypeTranslationDetailSerializer(serializers.ModelSerializer):
    source_unit = ContentUnitSerializer(read_only=True)
    source_text = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = StepTypeTranslation
        fields = ['source_text', 'source_unit', 'answers']

    def get_source_text(self, obj):
        lang = self.context.get('lang', 'en')
        if getattr(obj, 'source_group', None):
            return get_cached_translation(obj.source_group, lang)
        if obj.source_unit:
            return get_cached_translation(obj.source_unit.text_group, lang) or obj.source_unit.text
        return getattr(obj, 'source_text', None)

    def get_answers(self, obj):
        lang = self.context.get('lang', 'en')
        rel_answers = list(obj.relational_answers.all())
        
        if rel_answers:
            primaries = []
            for ans in rel_answers:
                if ans.is_primary:
                    text = get_cached_translation(ans.translation_group, lang) if ans.translation_group else ans.text_fallback
                    if text:
                        primaries.append(text)
            return primaries if primaries else []
            
        return obj.acceptable_answers


class SpeakPhraseDetailSerializer(serializers.ModelSerializer):
    target_unit = ContentUnitSerializer(read_only=True)
    reference_audio = AssetSerializer(read_only=True)
    target_text = serializers.SerializerMethodField()

    class Meta:
        model = StepSpeakPhrase
        fields = ['target_text', 'target_unit', 'reference_audio', 'min_score_required', 'allow_retry']

    def get_target_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.target_text_group:
            return get_cached_translation(obj.target_text_group, lang)
        if obj.target_unit:
            return get_cached_translation(obj.target_unit.text_group, lang) or obj.target_unit.text
        return obj.target_text


class LessonStepSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()
    prompt_text = serializers.SerializerMethodField()
    instruction_text = serializers.SerializerMethodField()
    hint = serializers.SerializerMethodField()
    grammar_note = serializers.SerializerMethodField()

    class Meta:
        model = LessonStep
        fields = [
            'id', 'step_type', 'prompt_text', 'instruction_text', 
            'xp_reward', 'sort_order', 'content', 'difficulty', 
            'cefr_level', 'hint', 'grammar_note', 'is_optional'
        ]

    def get_prompt_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.prompt_group:
            return get_cached_translation(obj.prompt_group, lang) or obj.prompt
        return obj.prompt

    def get_instruction_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.instruction_group:
            return get_cached_translation(obj.instruction_group, lang) or obj.instruction
        return obj.instruction

    def get_hint(self, obj):
        lang = self.context.get('lang', 'en')
        return get_cached_translation(obj.hint_group, lang) if obj.hint_group else None

    def get_grammar_note(self, obj):
        lang = self.context.get('lang', 'en')
        return get_cached_translation(obj.grammar_note_group, lang) if obj.grammar_note_group else None

    def get_content(self, obj):
        from ..registry import StepRegistry
        config = StepRegistry.get(obj.step_type)
        if not config:
            return None
        
        detail = getattr(obj, config.relation_name, None)
        if not detail:
            return None
            
        serializer = config.serializer_class(detail, context=self.context)
        return serializer.data
