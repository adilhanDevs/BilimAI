from django.db import transaction
from django.core.exceptions import ValidationError
from ..models.course import Lesson
from ..models.engine import LessonStep
from ..registry import StepRegistry


class ContentAuthoringService:
    """
    Service layer for safe content creation and management.
    Ensures that steps and their details are created/cloned atomically.
    """

    @staticmethod
    @transaction.atomic
    def create_lesson_step(lesson: Lesson, step_type: str, detail_data: dict = None, **step_kwargs):
        """
        Safely creates a LessonStep and its corresponding detail model.
        Supports creating nested child records (choices, pairs, tokens) via detail_data.
        """
        config = StepRegistry.get(step_type)
        if not config:
            raise ValidationError(f"Unsupported step_type: {step_type}")

        detail_data = detail_data or {}
        
        # Extract child records data to prevent them being passed to detail_model.objects.create
        choices_data = detail_data.pop('choices', [])
        pairs_data = detail_data.pop('pairs', [])
        tokens_data = detail_data.pop('tokens', [])

        # 1. Create Step
        step = LessonStep.objects.create(
            lesson=lesson,
            step_type=step_type,
            **step_kwargs
        )

        # 2. Create Detail record if relation exists
        if config.relation_name:
            # Dynamically find the model class via the relation
            detail_model = LessonStep._meta.get_field(config.relation_name).related_model
            
            # Create instance but don't save yet to allow validation
            detail_obj = detail_model(
                step=step,
                **detail_data
            )
            
            # Validate before saving to raise clear ValidationError instead of IntegrityError
            try:
                detail_obj.full_clean()
            except ValidationError as e:
                # Re-raise with more context if needed
                raise ValidationError(f"Invalid detail data for {step_type}: {e.message_dict}")
            
            detail_obj.save()

            # 3. Handle nested child records
            if step_type == 'multiple_choice' and choices_data:
                from ..models.engine import StepChoice
                for i, choice in enumerate(choices_data):
                    StepChoice.objects.create(
                        step_detail=detail_obj,
                        sort_order=i,
                        **choice
                    )
            elif step_type == 'match_pairs' and pairs_data:
                from ..models.engine import MatchPairItem
                for i, pair in enumerate(pairs_data):
                    MatchPairItem.objects.create(
                        step_detail=detail_obj,
                        sort_order=i,
                        **pair
                    )
            elif step_type == 'reorder_sentence' and tokens_data:
                from ..models.engine import ReorderToken
                for i, token in enumerate(tokens_data):
                    ReorderToken.objects.create(
                        step_detail=detail_obj,
                        sort_order=i,
                        **token
                    )
            
        return step

    @staticmethod
    @transaction.atomic
    def clone_lesson(lesson: Lesson, new_title: str = None):
        """
        Deep clones a lesson including all its steps and their details.
        Does NOT clone reusable ContentUnits or Assets (only references them).
        """
        original_steps = list(lesson.steps.all().order_by('sort_order'))
        
        # 1. Clone base Lesson
        lesson.pk = None
        lesson.id = None # Let UUID generate
        if new_title:
            lesson.title = new_title
            lesson.slug = f"{lesson.slug}-clone" # Basic slug handling
        lesson.save()

        # 2. Clone Steps
        for step in original_steps:
            original_detail = step.detail
            
            # Clone Step
            step.pk = None
            step.id = None
            step.lesson = lesson
            step.save()

            # Clone Detail
            if original_detail:
                # IMPORTANT: Fetch children BEFORE clearing PK
                children = []
                if step.step_type == 'multiple_choice':
                    children = list(original_detail.choices.all())
                elif step.step_type == 'match_pairs':
                    children = list(original_detail.pairs.all())
                elif step.step_type == 'reorder_sentence':
                    children = list(original_detail.tokens.all())

                original_detail.pk = None
                original_detail.id = None
                original_detail.step = step
                original_detail.save()
                
                # Clone nested child items (choices, pairs, tokens)
                for child in children:
                    child.pk = None
                    child.id = None # Just in case it's a UUID too
                    child.step_detail = original_detail
                    child.save()

        return lesson
