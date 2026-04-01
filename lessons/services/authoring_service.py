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
        """
        config = StepRegistry.get(step_type)
        if not config:
            raise ValidationError(f"Unsupported step_type: {step_type}")

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
            detail_obj = detail_model.objects.create(
                step=step,
                **(detail_data or {})
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
