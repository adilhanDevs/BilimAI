import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lessons.models import (
    Course,
    Category,
    Lesson,
    LessonVocabulary,
    LessonStep,
    StepMultipleChoice,
    StepChoice,
    StepFillBlank,
    StepMatchPairs,
    MatchPairItem,
    StepReorderSentence,
    ReorderToken,
    StepTypeTranslation,
    StepSpeakPhrase,
)


ALLOWED_STEP_TYPES = {
    "multiple_choice",
    "fill_blank",
    "match_pairs",
    "reorder_sentence",
    "type_translation",
    "speak_phrase",
}


class Command(BaseCommand):
    help = "Import one lesson from JSON into the lessons app."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to the lesson JSON file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print actions without saving to DB",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="If lesson exists, replace vocabulary and steps",
        )

    def handle(self, *args, **options):
        json_path = Path(options["json_path"])
        dry_run = options["dry_run"]
        replace = options["replace"]

        if not json_path.exists():
            raise CommandError(f"File not found: {json_path}")

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        self._validate_payload(payload)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE: no DB changes will be made."))

        if dry_run:
            self._print_summary(payload)
            self.stdout.write(self.style.SUCCESS("Validation passed."))
            return

        with transaction.atomic():
            course = self._upsert_course(payload["course"])
            category = self._upsert_category(payload["category"], course)
            lesson = self._upsert_lesson(payload["lesson"], category, replace=replace)

            if replace:
                self._clear_existing_lesson_content(lesson)

            self._import_vocabulary(lesson, payload.get("vocabulary", []))
            self._import_steps(lesson, payload.get("steps", []))

        self.stdout.write(self.style.SUCCESS(f"Lesson imported successfully: {lesson.slug}"))

    # ----------------------------
    # Validation
    # ----------------------------

    def _validate_payload(self, payload: Dict[str, Any]) -> None:
        required_top = ["course", "category", "lesson", "vocabulary", "steps"]
        for key in required_top:
            if key not in payload:
                raise CommandError(f"Missing top-level key: {key}")

        self._validate_course(payload["course"])
        self._validate_category(payload["category"])
        self._validate_lesson(payload["lesson"])
        self._validate_vocabulary(payload["vocabulary"])
        self._validate_steps(payload["steps"])

    def _validate_course(self, course: Dict[str, Any]) -> None:
        required = [
            "slug",
            "title",
            "source_language",
            "target_language",
            "cefr_min",
            "cefr_max",
            "description_ky",
        ]
        self._require_fields("course", course, required)

    def _validate_category(self, category: Dict[str, Any]) -> None:
        required = [
            "slug",
            "title_ky",
            "title_target",
            "description_ky",
            "sort_order",
            "estimated_minutes",
            "vocabulary_count",
        ]
        self._require_fields("category", category, required)

    def _validate_lesson(self, lesson: Dict[str, Any]) -> None:
        required = [
            "slug",
            "title",
            "subtitle",
            "description_ky",
            "level",
            "difficulty",
            "duration_min",
            "xp_reward",
            "grammar_focus",
            "sort_order",
        ]
        self._require_fields("lesson", lesson, required)

    def _validate_vocabulary(self, vocabulary: List[Dict[str, Any]]) -> None:
        if not isinstance(vocabulary, list):
            raise CommandError("vocabulary must be a list")

        for idx, item in enumerate(vocabulary, start=1):
            required = [
                "sort_order",
                "word_or_phrase_target",
                "translation_ky",
                "transliteration",
                "part_of_speech",
                "example_target",
                "example_ky",
                "audio_url",
            ]
            self._require_fields(f"vocabulary[{idx}]", item, required)

    def _validate_steps(self, steps: List[Dict[str, Any]]) -> None:
        if not isinstance(steps, list):
            raise CommandError("steps must be a list")

        if len(steps) != 21:
            raise CommandError(f"Each lesson must contain exactly 21 steps. Got: {len(steps)}")

        seen_orders = set()
        scenes = set()

        for idx, step in enumerate(steps, start=1):
            required = [
                "sort_order",
                "scene",
                "scene_title",
                "step_type",
                "prompt",
                "instruction",
                "xp_reward",
                "data",
            ]
            self._require_fields(f"steps[{idx}]", step, required)

            sort_order = step["sort_order"]
            if sort_order in seen_orders:
                raise CommandError(f"Duplicate step sort_order: {sort_order}")
            seen_orders.add(sort_order)

            scenes.add(step["scene"])

            step_type = step["step_type"]
            if step_type not in ALLOWED_STEP_TYPES:
                raise CommandError(f"Unsupported step_type: {step_type}")

            validator = getattr(self, f"_validate_step_{step_type}", None)
            if validator is None:
                raise CommandError(f"No validator implemented for step_type: {step_type}")
            validator(step["data"], idx)

        if scenes != {1, 2, 3, 4, 5, 6, 7}:
            raise CommandError(f"Lesson must contain scenes 1..7 exactly. Got: {sorted(scenes)}")

    def _validate_step_multiple_choice(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(f"steps[{idx}].data", data, ["selection_mode", "choices"])
        choices = data["choices"]
        if not isinstance(choices, list) or not choices:
            raise CommandError(f"steps[{idx}].data.choices must be a non-empty list")
        if not any(choice.get("is_correct") for choice in choices):
            raise CommandError(f"steps[{idx}] multiple_choice must have at least one correct choice")

    def _validate_step_fill_blank(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(
            f"steps[{idx}].data",
            data,
            ["source_text", "sentence_template", "acceptable_answers"],
        )
        if "[[blank]]" not in data["sentence_template"]:
            raise CommandError(f"steps[{idx}] fill_blank.sentence_template must contain [[blank]]")
        if not data["acceptable_answers"]:
            raise CommandError(f"steps[{idx}] fill_blank.acceptable_answers cannot be empty")

    def _validate_step_match_pairs(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(f"steps[{idx}].data", data, ["pairs"])
        pairs = data["pairs"]
        if not isinstance(pairs, list) or not pairs:
            raise CommandError(f"steps[{idx}] match_pairs.pairs must be a non-empty list")

    def _validate_step_reorder_sentence(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(f"steps[{idx}].data", data, ["tokens", "correct_sentence"])
        tokens = data["tokens"]
        if not isinstance(tokens, list) or not tokens:
            raise CommandError(f"steps[{idx}] reorder_sentence.tokens must be a non-empty list")

    def _validate_step_type_translation(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(f"steps[{idx}].data", data, ["source_text", "acceptable_answers"])
        if not data["acceptable_answers"]:
            raise CommandError(f"steps[{idx}] type_translation.acceptable_answers cannot be empty")

    def _validate_step_speak_phrase(self, data: Dict[str, Any], idx: int) -> None:
        self._require_fields(
            f"steps[{idx}].data",
            data,
            ["target_text", "reference_audio", "min_score_required", "allow_retry"],
        )

    def _require_fields(self, object_name: str, obj: Dict[str, Any], fields: List[str]) -> None:
        for field in fields:
            if field not in obj:
                raise CommandError(f"Missing field {object_name}.{field}")

    # ----------------------------
    # Upserts
    # ----------------------------

    def _upsert_course(self, data: Dict[str, Any]) -> Course:
        course, created = Course.objects.update_or_create(
            slug=data["slug"],
            defaults={
                "title": data["title"],
                "source_language": data["source_language"],
                "target_language": data["target_language"],
                "cefr_min": data["cefr_min"],
                "cefr_max": data["cefr_max"],
                "description_ky": data["description_ky"],
                "is_published": True,
            },
        )
        self.stdout.write(
            f"{'Created' if created else 'Updated'} course: {course.slug}"
        )
        return course

    def _upsert_category(self, data: Dict[str, Any], course: Course) -> Category:
        category, created = Category.objects.update_or_create(
            course=course,
            slug=data["slug"],
            defaults={
                "title_ky": data["title_ky"],
                "title_target": data["title_target"],
                "description_ky": data["description_ky"],
                "sort_order": data["sort_order"],
                "estimated_minutes": data["estimated_minutes"],
                "vocabulary_count": data["vocabulary_count"],
                "is_premium": False,
            },
        )
        self.stdout.write(
            f"{'Created' if created else 'Updated'} category: {category.slug}"
        )
        return category

    def _upsert_lesson(self, data: Dict[str, Any], category: Category, replace: bool) -> Lesson:
        lesson = Lesson.objects.filter(category=category, slug=data["slug"]).first()

        if lesson and not replace:
            raise CommandError(
                f"Lesson already exists: {lesson.slug}. Use --replace to overwrite vocabulary and steps."
            )

        if lesson:
            for field, value in {
                "title": data["title"],
                "subtitle": data["subtitle"],
                "description_ky": data["description_ky"],
                "level": data["level"],
                "difficulty": data["difficulty"],
                "duration_min": data["duration_min"],
                "xp_reward": data["xp_reward"],
                "grammar_focus": data["grammar_focus"],
                "sort_order": data["sort_order"],
                "is_published": True,
                "is_premium": False,
            }.items():
                setattr(lesson, field, value)
            lesson.save()
            self.stdout.write(f"Updated lesson: {lesson.slug}")
            return lesson

        lesson = Lesson.objects.create(
            category=category,
            slug=data["slug"],
            title=data["title"],
            subtitle=data["subtitle"],
            description_ky=data["description_ky"],
            level=data["level"],
            difficulty=data["difficulty"],
            duration_min=data["duration_min"],
            xp_reward=data["xp_reward"],
            grammar_focus=data["grammar_focus"],
            sort_order=data["sort_order"],
            is_published=True,
            is_premium=False,
        )
        self.stdout.write(f"Created lesson: {lesson.slug}")
        return lesson

    # ----------------------------
    # Cleanup
    # ----------------------------

    def _clear_existing_lesson_content(self, lesson: Lesson) -> None:
        # Delete step details first, then steps, then vocabulary.
        # Using explicit cleanup keeps behavior predictable.
        for step in lesson.steps.all():
            StepChoice.objects.filter(step_detail__step=step).delete()
            StepMultipleChoice.objects.filter(step=step).delete()

            MatchPairItem.objects.filter(step_detail__step=step).delete()
            StepMatchPairs.objects.filter(step=step).delete()

            ReorderToken.objects.filter(step_detail__step=step).delete()
            StepReorderSentence.objects.filter(step=step).delete()

            StepFillBlank.objects.filter(step=step).delete()
            StepTypeTranslation.objects.filter(step=step).delete()
            StepSpeakPhrase.objects.filter(step=step).delete()

        lesson.steps.all().delete()
        lesson.vocabulary.all().delete()

        self.stdout.write(f"Cleared existing vocabulary and steps for lesson: {lesson.slug}")

    # ----------------------------
    # Import vocabulary
    # ----------------------------

    def _import_vocabulary(self, lesson: Lesson, vocabulary: List[Dict[str, Any]]) -> None:
        for item in vocabulary:
            LessonVocabulary.objects.create(
                lesson=lesson,
                sort_order=item["sort_order"],
                word_or_phrase_target=item["word_or_phrase_target"],
                translation_ky=item["translation_ky"],
                transliteration=item["transliteration"],
                part_of_speech=item["part_of_speech"],
                example_target=item["example_target"],
                example_ky=item["example_ky"],
                audio_url=item["audio_url"],
            )

        self.stdout.write(f"Imported vocabulary: {len(vocabulary)} items")

    # ----------------------------
    # Import steps
    # ----------------------------

    def _import_steps(self, lesson: Lesson, steps: List[Dict[str, Any]]) -> None:
        for step_payload in steps:
            step = LessonStep.objects.create(
                lesson=lesson,
                step_type=step_payload["step_type"],
                prompt=step_payload["prompt"],
                instruction=step_payload["instruction"],
                sort_order=step_payload["sort_order"],
                xp_reward=step_payload["xp_reward"],
            )

            handler = getattr(self, f"_create_{step_payload['step_type']}_detail")
            handler(step, step_payload["data"])

        self.stdout.write(f"Imported steps: {len(steps)} items")

    def _create_multiple_choice_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        from ...models.engine import ContentUnit, Asset
        
        # Check if this is a "choose what you heard" step
        source_unit = None
        if "audio" in data.get("prompt_text", "").lower() or "послушайте" in data.get("prompt_text", "").lower():
            mock_audio, _ = Asset.objects.get_or_create(
                file='test.mp3',
                defaults={'asset_type': 'audio'}
            )
            source_unit = ContentUnit.objects.create(
                unit_type='audio_prompt',
                text="Audio Prompt",
                primary_audio=mock_audio
            )

        detail = StepMultipleChoice.objects.create(
            step=lesson_step,
            source_unit=source_unit
        )
        for choice in data["choices"]:
            StepChoice.objects.create(
                step_detail=detail,
                text=choice["text"],
                is_correct=choice["is_correct"],
                sort_order=choice["sort_order"],
            )

    def _create_fill_blank_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        from ...models.engine import ContentUnit, Asset
        
        source_unit = None
        # Logic to decide if fill_blank needs audio mock
        # For demo, let's add it if not present
        mock_audio, _ = Asset.objects.get_or_create(
            file='test.mp3',
            defaults={'asset_type': 'audio'}
        )
        source_unit = ContentUnit.objects.create(
            unit_type='sentence',
            text=data["sentence_template"],
            primary_audio=mock_audio
        )

        StepFillBlank.objects.create(
            step=lesson_step,
            sentence_template=data["sentence_template"],
            acceptable_answers=data["acceptable_answers"],
            source_unit=source_unit
        )

    def _create_match_pairs_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        from ...models.engine import ContentUnit, Asset
        detail = StepMatchPairs.objects.create(step=lesson_step)
        
        # Mock asset for demonstration
        mock_audio, _ = Asset.objects.get_or_create(
            file='test.mp3',
            defaults={'asset_type': 'audio'}
        )

        for pair in data["pairs"]:
            # Create a ContentUnit to hold the mock audio
            left_unit = ContentUnit.objects.create(
                unit_type='word',
                text=pair["left_text"],
                primary_audio=mock_audio
            )
            
            MatchPairItem.objects.create(
                step_detail=detail,
                left_text=pair["left_text"],
                right_text=pair["right_text"],
                left_content_unit=left_unit,
                sort_order=pair["sort_order"],
            )

    def _create_reorder_sentence_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        detail = StepReorderSentence.objects.create(
            step=lesson_step,
        )
        for token in data["tokens"]:
            ReorderToken.objects.create(
                step_detail=detail,
                text=token["text"],
                is_distractor=token["is_distractor"],
                sort_order=token["sort_order"],
            )

    def _create_type_translation_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        StepTypeTranslation.objects.create(
            step=lesson_step,
            source_text=data["source_text"],
            acceptable_answers=data["acceptable_answers"],
        )

    def _create_speak_phrase_detail(self, lesson_step: LessonStep, data: Dict[str, Any]) -> None:
        StepSpeakPhrase.objects.create(
            step=lesson_step,
            target_text=data["target_text"],
            reference_audio_id=data.get("reference_audio"),
            min_score_required=data["min_score_required"],
            allow_retry=data["allow_retry"],
        )

    # ----------------------------
    # Dry-run output
    # ----------------------------

    def _print_summary(self, payload: Dict[str, Any]) -> None:
        self.stdout.write("=== IMPORT SUMMARY ===")
        self.stdout.write(f"Course:   {payload['course']['slug']}")
        self.stdout.write(f"Category: {payload['category']['slug']}")
        self.stdout.write(f"Lesson:   {payload['lesson']['slug']}")
        self.stdout.write(f"Vocabulary items: {len(payload['vocabulary'])}")
        self.stdout.write(f"Steps: {len(payload['steps'])}")