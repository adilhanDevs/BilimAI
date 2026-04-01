from rest_framework import serializers
from .base import AssetSerializer, ContentUnitSerializer, CourseSerializer
from .steps import (
    MultipleChoiceDetailSerializer, FillBlankDetailSerializer,
    MatchPairsDetailSerializer, ReorderSentenceDetailSerializer,
    TypeTranslationDetailSerializer, SpeakPhraseDetailSerializer
)
from .sessions import (
    LessonProgressSerializer, SessionStatusSerializer,
    SpeechSubmissionStatusSerializer, SpeechSubmissionRequestSerializer,
    SpeechSubmissionResponseSerializer,
    AttemptRequestSerializer, AttemptResponseSerializer,
    ReviewItemSerializer, CourseSummarySerializer
)
from ..models.engine import LessonStep
from ..utils import get_translation


class LessonStepSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()
    prompt_text = serializers.SerializerMethodField()
    instruction_text = serializers.SerializerMethodField()

    class Meta:
        model = LessonStep
        fields = ['id', 'step_type', 'prompt_text', 'instruction_text', 'sort_order', 'xp_reward', 'content']

    def get_prompt_text(self, obj):
        lang = self.context.get('lang', 'en')
        return get_translation(obj.prompt_group, lang, obj.prompt)

    def get_instruction_text(self, obj):
        lang = self.context.get('lang', 'en')
        return get_translation(obj.instruction_group, lang, obj.instruction)

    def get_content(self, obj):
        from ..registry import StepRegistry
        config = StepRegistry.get(obj.step_type)
        if not config or not config.serializer_class:
            return None
        
        detail_obj = getattr(obj, config.relation_name, None)
        if not detail_obj:
            return None
            
        return config.serializer_class(detail_obj, context=self.context).data
