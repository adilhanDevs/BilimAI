from dataclasses import dataclass, field
from typing import Type, Dict, List, Optional, Callable, Any
from rest_framework import serializers


@dataclass
class StepConfiguration:
    step_type: str
    relation_name: str
    serializer_class: Type[serializers.Serializer]
    evaluator_class: Type['BaseStepEvaluator']
    select_related_paths: List[str] = field(default_factory=list)
    prefetch_related_paths: List[str] = field(default_factory=list)
    # New: Function to extract ContentUnits from a step for mastery updates
    content_extractor: Optional[Callable[[Any, Dict[str, Any]], List['ContentUnit']]] = None
    # New: Skills this step type contributes to
    skill_contributions: List[str] = field(default_factory=lambda: ['vocabulary'])


class StepRegistry:
    _registry: Dict[str, StepConfiguration] = {}

    @classmethod
    def register(cls, config: StepConfiguration):
        cls._registry[config.step_type] = config

    @classmethod
    def get(cls, step_type: str) -> Optional[StepConfiguration]:
        return cls._registry.get(step_type)

    @classmethod
    def get_all_configs(cls) -> List[StepConfiguration]:
        return list(cls._registry.values())

    @classmethod
    def get_optimized_prefetches(cls, lang=None):
        """
        Generates advanced Prefetch objects for LessonStep based on registered types.
        """
        from django.db.models import Prefetch
        from .models.engine import ContentUnit, StepChoice, MatchPairItem, ReorderToken
        from .models.localization import Translation
        
        # Base queryset for ContentUnits with localized translations if requested
        cu_qs = ContentUnit.objects.select_related('text_group', 'meaning_group', 'primary_audio', 'primary_image')
        
        translation_qs = None
        if lang:
            translation_qs = Translation.objects.filter(language_id=lang)
            cu_qs = cu_qs.prefetch_related(
                Prefetch('text_group__translations', queryset=translation_qs, to_attr='active_translations'),
                Prefetch('meaning_group__translations', queryset=translation_qs, to_attr='active_translations')
            )
        
        prefetch_related = []
        
        for config in cls._registry.values():
            rel = config.relation_name
            
            if config.step_type == 'multiple_choice':
                choice_qs = StepChoice.objects.prefetch_related(Prefetch('content_unit', queryset=cu_qs))
                prefetch_related.append(Prefetch(f"{rel}__choices", queryset=choice_qs))
            elif config.step_type == 'fill_blank':
                prefetch_related.append(Prefetch(f"{rel}__source_unit", queryset=cu_qs))
            elif config.step_type == 'match_pairs':
                pair_qs = MatchPairItem.objects.prefetch_related(
                    Prefetch('left_content_unit', queryset=cu_qs),
                    Prefetch('right_content_unit', queryset=cu_qs)
                )
                prefetch_related.append(Prefetch(f"{rel}__pairs", queryset=pair_qs))
            elif config.step_type == 'reorder_sentence':
                token_qs = ReorderToken.objects.prefetch_related(Prefetch('content_unit', queryset=cu_qs))
                prefetch_related.append(Prefetch(f"{rel}__tokens", queryset=token_qs))
            elif config.step_type == 'type_translation':
                prefetch_related.append(Prefetch(f"{rel}__source_unit", queryset=cu_qs))
            elif config.step_type == 'speak_phrase':
                prefetch_related.append(Prefetch(f"{rel}__target_unit", queryset=cu_qs))
                if lang:
                    prefetch_related.append(Prefetch(f"{rel}__target_text_group__translations", queryset=translation_qs, to_attr='active_translations'))
                else:
                    prefetch_related.append(f"{rel}__target_text_group")
                prefetch_related.append(f"{rel}__reference_audio")

        return prefetch_related


# To avoid circular imports, we import and register after definition
def initialize_registry():
    from .serializers import (
        MultipleChoiceDetailSerializer, FillBlankDetailSerializer,
        MatchPairsDetailSerializer, ReorderSentenceDetailSerializer,
        TypeTranslationDetailSerializer, SpeakPhraseDetailSerializer
    )
    from .evaluators import (
        MultipleChoiceEvaluator, FillBlankEvaluator, MatchPairsEvaluator,
        ReorderSentenceEvaluator, TypeTranslationEvaluator, SpeakPhraseEvaluator
    )

    # --- Extractors ---

    def mc_extractor(detail, payload):
        selected_id = payload.get('selected_choice_id')
        if not selected_id: return []
        
        # If the attempt is handled as correct (caller should handle result mapping), 
        # we might want only the correct one. But the generic extractor doesn't know 'is_correct' yet.
        # Let's adjust the extractor to return the SELECTED unit always.
        choices = detail.choices.all()
        choice = next((c for c in choices if str(c.id) == str(selected_id)), None)
        
        if choice and choice.content_unit:
            return [choice.content_unit]
        return []

    def source_unit_extractor(detail, payload):
        return [detail.source_unit] if detail.source_unit else []

    def speak_extractor(detail, payload):
        return [detail.target_unit] if detail.target_unit else []

    def pairs_extractor(detail, payload):
        # Could extract all pairs or just those involved if payload specifies
        units = []
        for p in detail.pairs.all():
            if p.left_content_unit: units.append(p.left_content_unit)
            if p.right_content_unit: units.append(p.right_content_unit)
        return units

    def reorder_extractor(detail, payload):
        return [t.content_unit for t in detail.tokens.all() if t.content_unit]

    # --- Registration ---

    StepRegistry.register(StepConfiguration(
        step_type='multiple_choice',
        relation_name='detail_multiple_choice',
        serializer_class=MultipleChoiceDetailSerializer,
        evaluator_class=MultipleChoiceEvaluator,
        content_extractor=mc_extractor,
        skill_contributions=['vocabulary', 'reading'],
        prefetch_related_paths=[
            'choices',
            'choices__content_unit__text_group',
            'choices__content_unit__meaning_group',
            'choices__content_unit__primary_audio',
            'choices__content_unit__primary_image'
        ]
    ))

    StepRegistry.register(StepConfiguration(
        step_type='fill_blank',
        relation_name='detail_fill_blank',
        serializer_class=FillBlankDetailSerializer,
        evaluator_class=FillBlankEvaluator,
        content_extractor=source_unit_extractor,
        skill_contributions=['vocabulary', 'grammar', 'reading'],
        prefetch_related_paths=[
            'source_unit__text_group',
            'source_unit__meaning_group',
            'source_unit__primary_audio',
            'source_unit__primary_image'
        ]
    ))

    StepRegistry.register(StepConfiguration(
        step_type='match_pairs',
        relation_name='detail_match_pairs',
        serializer_class=MatchPairsDetailSerializer,
        evaluator_class=MatchPairsEvaluator,
        content_extractor=pairs_extractor,
        skill_contributions=['vocabulary', 'reading'],
        prefetch_related_paths=[
            'pairs',
            'pairs__left_content_unit__text_group',
            'pairs__left_content_unit__meaning_group',
            'pairs__left_content_unit__primary_audio',
            'pairs__left_content_unit__primary_image',
            'pairs__right_content_unit__text_group',
            'pairs__right_content_unit__meaning_group',
            'pairs__right_content_unit__primary_audio',
            'pairs__right_content_unit__primary_image',
        ]
    ))

    StepRegistry.register(StepConfiguration(
        step_type='reorder_sentence',
        relation_name='detail_reorder_sentence',
        serializer_class=ReorderSentenceDetailSerializer,
        evaluator_class=ReorderSentenceEvaluator,
        content_extractor=reorder_extractor,
        skill_contributions=['grammar', 'writing'],
        prefetch_related_paths=[
            'tokens',
            'tokens__content_unit__text_group',
            'tokens__content_unit__meaning_group',
            'tokens__content_unit__primary_audio',
            'tokens__content_unit__primary_image',
        ]
    ))

    StepRegistry.register(StepConfiguration(
        step_type='type_translation',
        relation_name='detail_type_translation',
        serializer_class=TypeTranslationDetailSerializer,
        evaluator_class=TypeTranslationEvaluator,
        content_extractor=source_unit_extractor,
        skill_contributions=['vocabulary', 'writing'],
        prefetch_related_paths=[
            'source_unit__text_group',
            'source_unit__meaning_group',
            'source_unit__primary_audio',
            'source_unit__primary_image',
        ]
    ))

    StepRegistry.register(StepConfiguration(
        step_type='speak_phrase',
        relation_name='detail_speak_phrase',
        serializer_class=SpeakPhraseDetailSerializer,
        evaluator_class=SpeakPhraseEvaluator,
        content_extractor=speak_extractor,
        skill_contributions=['speaking'],
        prefetch_related_paths=[
            'target_unit__text_group',
            'target_unit__meaning_group',
            'target_unit__primary_audio',
            'target_unit__primary_image',
            'target_text_group',
            'reference_audio',
        ]
    ))

# Call initialization
initialize_registry()
