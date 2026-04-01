from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Max
from ..models.progress import (
    LessonSession, StepAttempt, 
    UserLessonProgress, UserContentProgress
)
from ..models.engine import LessonStep, ContentUnit


class SRSSchedulingService:
    @staticmethod
    def get_next_review_at(is_correct: bool, current_mastery: int):
        """
        Simple initial SRS logic.
        """
        now = timezone.now()
        if is_correct:
            # Simple progressive intervals
            if current_mastery < 20:
                return now + timedelta(days=1)
            elif current_mastery < 50:
                return now + timedelta(days=3)
            elif current_mastery < 80:
                return now + timedelta(days=7)
            else:
                return now + timedelta(days=14)
        else:
            # Reset/short interval on mistake
            return now + timedelta(hours=4)


class ProgressTrackingService:
    @staticmethod
    @transaction.atomic
    def update_progress_after_attempt(attempt: StepAttempt):
        """
        Main entry point for updating all progress models after an attempt.
        Wired to update domain-level progress (Skills, Categories, Review Queue).
        """
        session = attempt.session
        user = session.user
        step = attempt.step
        
        # 1. Prevent updates on inactive sessions
        if session.status != 'active':
            return

        # Check if user already got this step correct in this session (Idempotency)
        # We only care about this if the CURRENT attempt is correct
        already_correct = False
        if attempt.is_correct:
            already_correct = StepAttempt.objects.filter(
                session=session, step=step, is_correct=True
            ).exclude(id=attempt.id).exists()

        # 2. Update Session Gamification
        if attempt.is_correct:
            if not already_correct:
                session.xp_earned += step.xp_reward
                # Use a more robust check for completed count
                session.completed_steps_count = StepAttempt.objects.filter(
                    session=session, is_correct=True
                ).values('step').distinct().count()
        else:
            session.hearts_remaining = max(0, session.hearts_remaining - 1)
            session.mistakes_count += 1
            
        # Check session failure
        if session.is_failed:
            session.status = 'failed'
            session.completed_at = timezone.now()
        else:
            # Idempotent completion check
            total_steps = getattr(session, 'total_steps_count', None)
            if total_steps is None:
                total_steps = step.lesson.steps.count()
            
            if session.completed_steps_count >= total_steps:
                session.status = 'completed'
                session.completed_at = timezone.now()
        
        session.save()

        # 3. Update UserLessonProgress (Aggregated)
        lesson_progress, _ = UserLessonProgress.objects.get_or_create(
            user=user, lesson=step.lesson
        )
        
        lesson_progress.total_attempts += 1
        if attempt.is_correct and not already_correct:
            lesson_progress.total_correct_attempts += 1
            lesson_progress.total_xp_earned += step.xp_reward
            
        if session.status == 'completed':
            lesson_progress.status = 'completed'
            if lesson_progress.completed_at is None:
                lesson_progress.completed_at = timezone.now()
            
            # Recalculate best score
            total_steps = getattr(session, 'total_steps_count', None) or step.lesson.steps.count()
            current_score = int((session.completed_steps_count / total_steps) * 100) if total_steps > 0 else 0
            lesson_progress.best_score = max(lesson_progress.best_score, current_score)
            
        lesson_progress.last_session = session
        lesson_progress.save()

        # --- Domain Integration Wiring ---

        # 4. Update UserContentProgress (Mastery) & Review Queue
        ProgressTrackingService._update_content_mastery(user, attempt)

        # 5. Update Skill Progress
        from .skill_progress_service import SkillProgressService
        SkillProgressService.update_skill_progress(attempt)

        # 6. If session completed, update Category Progress
        if session.status == 'completed':
            from .category_progress_service import CategoryProgressService
            CategoryProgressService.update_category_progress(user, step.lesson.category)

    @staticmethod
    def _update_content_mastery(user, attempt: StepAttempt):
        """
        Identifies relevant content units from the step and updates their mastery.
        Uses StepRegistry to handle step-type-specific extraction.
        """
        from ..registry import StepRegistry
        
        step = attempt.step
        config = StepRegistry.get(step.step_type)
        if not config or not config.content_extractor:
            return

        detail = getattr(step, config.relation_name, None)
        if not detail:
            return

        content_units = config.content_extractor(detail, attempt.client_payload)

        # Update each found unit
        for unit in content_units:
            content_progress, _ = UserContentProgress.objects.get_or_create(
                user=user, content_unit=unit
            )
            content_progress.exposure_count += 1
            if attempt.is_correct:
                content_progress.correct_count += 1
                content_progress.mastery_score = min(100, content_progress.mastery_score + 10)
            else:
                content_progress.incorrect_count += 1
                content_progress.mastery_score = max(0, content_progress.mastery_score - 5)
            
            # Schedule next review
            content_progress.next_review_at = SRSSchedulingService.get_next_review_at(
                attempt.is_correct, content_progress.mastery_score
            )
            content_progress.save()

            # Sync Review Queue
            from .review_queue_service import ReviewQueueService
            ReviewQueueService.sync_review_item(content_progress)
