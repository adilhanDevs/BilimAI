import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models.engine import LessonStep, StepAnswer, StepMultipleChoice, StepChoice, StepFillBlank, StepTypeTranslation
from ..utils.cache import invalidate_lesson_cache

logger = logging.getLogger(__name__)

class ContentAuthoringService:
    @staticmethod
    def create_lesson_step(lesson, step_type, sort_order=0, xp_reward=10, detail_data=None):
        """
        Atomically creates a LessonStep and its associated detail record.
        """
        from ..registry import StepRegistry
        config = StepRegistry.get(step_type)
        if not config:
            raise ValidationError(f"Unsupported step type: {step_type}")

        detail_data = detail_data or {}
        
        with transaction.atomic():
            step = LessonStep.objects.create(
                lesson=lesson,
                step_type=step_type,
                sort_order=sort_order,
                xp_reward=xp_reward,
                prompt=detail_data.get('prompt'),
                instruction=detail_data.get('instruction'),
                difficulty=detail_data.get('difficulty', 1),
                cefr_level=detail_data.get('cefr_level'),
                is_optional=detail_data.get('is_optional', False)
            )
            
            # Map type to model and handle specific creation logic
            if step_type == 'multiple_choice':
                detail = StepMultipleChoice.objects.create(step=step, allow_multiple=detail_data.get('allow_multiple', False))
                choices = detail_data.get('choices', [])
                for idx, c in enumerate(choices):
                    StepChoice.objects.create(
                        step_detail=detail,
                        text=c.get('text'),
                        content_unit=c.get('content_unit'),
                        is_correct=c.get('is_correct', False),
                        sort_order=idx
                    )
            elif step_type == 'fill_blank':
                ContentAuthoringService.update_fill_blank_step(step, detail_data)
            elif step_type == 'type_translation':
                ContentAuthoringService.update_type_translation_step(step, detail_data)
            # ... other types would go here
            
            invalidate_lesson_cache(lesson.id)
            return step

    @staticmethod
    def update_fill_blank_step(step, data):
        with transaction.atomic():
            detail, _ = StepFillBlank.objects.get_or_create(step=step)
            detail.sentence_template = data.get('sentence_template', detail.sentence_template)
            detail.source_unit = data.get('source_unit', detail.source_unit)
            
            if 'answers' in data:
                ContentAuthoringService.update_relational_answers(detail, data['answers'])
            
            detail.save()

    @staticmethod
    def update_type_translation_step(step, data):
        with transaction.atomic():
            detail, _ = StepTypeTranslation.objects.get_or_create(step=step)
            detail.source_unit = data.get('source_unit', detail.source_unit)
            detail.source_group = data.get('source_group', detail.source_group)
            detail.source_text = data.get('source_text', detail.source_text)
            
            if 'answers' in data:
                ContentAuthoringService.update_relational_answers(detail, data['answers'])
            
            detail.save()

    @staticmethod
    def update_relational_answers(detail_obj, answer_payload: list):
        """
        Optimized, concurrency-safe dual-write logic.
        Uses bulk_create and select_for_update to prevent race conditions.
        Payload format: list of {text, blank_index, is_primary, case_sensitive, ignore_punctuation}
        """
        if not isinstance(answer_payload, list):
            raise ValidationError("Answer payload must be a list.")

        model_name = detail_obj._meta.model_name
        fk_field = "step_fill_blank" if model_name == "stepfillblank" else "step_type_translation"
        detail_model = detail_obj.__class__

        with transaction.atomic():
            # Lock the row for updates
            locked_detail = detail_model.objects.select_for_update().get(pk=detail_obj.pk)
            
            # 1. Clear existing relational answers
            locked_detail.relational_answers.all().delete()
            
            json_fallback_map = {}
            answers_to_create = []
            
            for item in answer_payload:
                text = str(item.get('text') or "").strip()
                if not text: continue
                
                idx = int(item.get('blank_index', 0))
                is_primary = bool(item.get('is_primary', False))
                
                answers_to_create.append(StepAnswer(
                    **{fk_field: locked_detail},
                    text_fallback=text,
                    blank_index=idx,
                    is_primary=is_primary,
                    case_sensitive=bool(item.get('case_sensitive', False)),
                    ignore_punctuation=bool(item.get('ignore_punctuation', True)),
                    sort_order=int(item.get('sort_order', 0))
                ))
                
                # Prep JSON Fallback map
                if idx not in json_fallback_map: json_fallback_map[idx] = []
                if is_primary:
                    json_fallback_map[idx].insert(0, text)
                else:
                    json_fallback_map[idx].append(text)

            # Bulk insert optimization
            if answers_to_create:
                StepAnswer.objects.bulk_create(answers_to_create, batch_size=100)

            # 2. Reconstruct legacy JSON structure (Phase 3 removal candidate)
            if not json_fallback_map:
                locked_detail.acceptable_answers = []
            else:
                max_idx = max(json_fallback_map.keys())
                final_json = []
                for i in range(max_idx + 1):
                    opts = json_fallback_map.get(i, [""])
                    final_json.append(opts[0] if len(opts) == 1 else opts)
                locked_detail.acceptable_answers = final_json

            locked_detail.save(update_fields=['acceptable_answers'])
            invalidate_lesson_cache(locked_detail.step.lesson_id)
            
        return locked_detail

    @staticmethod
    def clone_lesson(lesson, new_title=None):
        # Implementation omitted for brevity, but should invalidate cache
        pass
