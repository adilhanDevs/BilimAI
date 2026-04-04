from django.core.management.base import BaseCommand
from django.db import transaction
from lessons.models.engine import StepFillBlank, StepTypeTranslation, StepAnswer

class Command(BaseCommand):
    help = "Migrates acceptable_answers JSON to relational StepAnswer table robustly"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Run without saving to DB')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        stats = {'scanned': 0, 'created': 0, 'skipped': 0, 'errors': 0}

        def process_step(step, fk_field):
            stats['scanned'] += 1
            answers = getattr(step, 'acceptable_answers', None)
            
            if not answers:
                return []

            if not isinstance(answers, list):
                self.stderr.write(f"Error: Expected list for {step.step.id}, got {type(answers)}")
                stats['errors'] += 1
                return []

            batch = []
            for idx, item in enumerate(answers):
                if isinstance(item, list):
                    # Multi-blank format
                    for sub_idx, text in enumerate(item):
                        text_str = str(text).strip() if text else ""
                        if text_str:
                            batch.append(self._prep_answer(step, fk_field, text_str, idx, sub_idx == 0))
                else:
                    # Single-blank format
                    text_str = str(item).strip() if item else ""
                    if text_str:
                        batch.append(self._prep_answer(step, fk_field, text_str, 0, idx == 0))
            return batch

        try:
            with transaction.atomic():
                all_to_create = []
                
                # Process FillBlank
                for step in StepFillBlank.objects.iterator():
                    # Check if already has relational answers to remain idempotent
                    if step.relational_answers.exists():
                        stats['skipped'] += 1
                        continue
                    all_to_create.extend(process_step(step, "step_fill_blank"))

                # Process TypeTranslation
                for step in StepTypeTranslation.objects.iterator():
                    if step.relational_answers.exists():
                        stats['skipped'] += 1
                        continue
                    all_to_create.extend(process_step(step, "step_type_translation"))
                
                if all_to_create and not dry_run:
                    # Batch create for performance
                    StepAnswer.objects.bulk_create(all_to_create, batch_size=500)
                    stats['created'] = len(all_to_create)
                elif dry_run:
                    stats['created'] = len(all_to_create)
                    self.stdout.write(self.style.WARNING("DRY RUN: Rolling back transaction."))
                    transaction.set_rollback(True)
                    
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Migration aborted due to error: {e}"))
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Done. Scanned steps: {stats['scanned']} | "
            f"Answers to create: {stats['created']} | "
            f"Steps skipped: {stats['skipped']} | "
            f"Errors: {stats['errors']}"
        ))

    def _prep_answer(self, detail, fk_field, text, blank_idx, is_primary):
        return StepAnswer(
            **{fk_field: detail},
            text_fallback=text,
            blank_index=blank_idx,
            is_primary=is_primary,
            sort_order=0 if is_primary else 10
        )
