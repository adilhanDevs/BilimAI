from rest_framework import serializers
from .base import ContentUnitSerializer, AssetSerializer
from ..models.engine import (
    StepMultipleChoice, StepChoice, StepFillBlank, StepMatchPairs,
    MatchPairItem, StepReorderSentence, ReorderToken, StepTypeTranslation,
    StepSpeakPhrase
)
from ..utils import get_translation


class StepChoiceSerializer(serializers.ModelSerializer):
    content_unit = ContentUnitSerializer(read_only=True)
    text = serializers.SerializerMethodField()

    class Meta:
        model = StepChoice
        fields = ['id', 'text', 'sort_order', 'content_unit']

    def get_text(self, obj):
        if obj.text:
            return obj.text
        if obj.content_unit:
            lang = self.context.get('lang', 'en')
            return get_translation(obj.content_unit.text_group, lang, obj.content_unit.text)
        return None


class MultipleChoiceDetailSerializer(serializers.ModelSerializer):
    choices = StepChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = StepMultipleChoice
        fields = ['choices', 'allow_multiple']


class FillBlankDetailSerializer(serializers.ModelSerializer):
    source_unit = ContentUnitSerializer(read_only=True)

    class Meta:
        model = StepFillBlank
        fields = ['sentence_template', 'source_unit']


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
        if obj.left_text:
            return obj.left_text
        if obj.left_content_unit:
            return get_translation(obj.left_content_unit.text_group, lang, obj.left_content_unit.text)
        return None

    def get_right_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.right_text:
            return obj.right_text
        if obj.right_content_unit:
            return get_translation(obj.right_content_unit.text_group, lang, obj.right_content_unit.text)
        return None


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
        if obj.text:
            return obj.text
        if obj.content_unit:
            return get_translation(obj.content_unit.text_group, lang, obj.content_unit.text)
        return None


class ReorderSentenceDetailSerializer(serializers.ModelSerializer):
    tokens = ReorderTokenSerializer(many=True, read_only=True)

    class Meta:
        model = StepReorderSentence
        fields = ['tokens']


class TypeTranslationDetailSerializer(serializers.ModelSerializer):
    source_unit = ContentUnitSerializer(read_only=True)
    source_text = serializers.SerializerMethodField()

    class Meta:
        model = StepTypeTranslation
        fields = ['source_text', 'source_unit']

    def get_source_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.source_text:
            return obj.source_text
        if obj.source_unit:
            return get_translation(obj.source_unit.text_group, lang, obj.source_unit.text)
        return None


class SpeakPhraseDetailSerializer(serializers.ModelSerializer):
    target_unit = ContentUnitSerializer(read_only=True)
    reference_audio = AssetSerializer(read_only=True)
    target_text = serializers.SerializerMethodField()

    class Meta:
        model = StepSpeakPhrase
        fields = ['target_text', 'target_unit', 'reference_audio', 'min_score_required', 'allow_retry']

    def get_target_text(self, obj):
        lang = self.context.get('lang', 'en')
        if obj.target_text:
            return obj.target_text
        if obj.target_text_group:
            return get_translation(obj.target_text_group, lang, obj.target_text)
        if obj.target_unit:
            return get_translation(obj.target_unit.text_group, lang, obj.target_unit.text)
        return None
