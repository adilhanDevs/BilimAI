import logging
from typing import Dict, Any
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models.progress import LessonSession, StepAttempt, SpeechSubmission
from ..models.engine import LessonStep, StepSpeakPhrase
from ..registry import StepRegistry
from ..utils import get_translation

logger = logging.getLogger(__name__)


class SpeakingEvaluationService:
    @staticmethod
    def create_submission(user, session_id: str, step_id: str, audio_file) -> SpeechSubmission:
        """
        Validates the request and creates a pending SpeechSubmission.
        """
        try:
            # Enforce user ownership in query
            session = LessonSession.objects.get(id=session_id, user=user)
        except (LessonSession.DoesNotExist, ValidationError):
            logger.warning(f"Speaking submission failed: Session {session_id} not found for user {user.id}.")
            raise ValidationError("Session not found.")

        if session.status != 'active':
            logger.info(f"Speaking submission rejected: Session {session_id} is {session.status}.")
            raise ValidationError("Session is no longer active.")

        # Enrollment Check
        from .course_enrollment_service import CourseEnrollmentService
        if not CourseEnrollmentService.is_enrolled(user, session.lesson.category.course):
            logger.warning(f"Speaking submission rejected: User {user.id} not enrolled in course {session.lesson.category.course_id}.")
            raise ValidationError("User is not enrolled in this course.")

        try:
            step = LessonStep.objects.get(id=step_id, step_type='speak_phrase')
        except (LessonStep.DoesNotExist, ValidationError):
            logger.warning(f"Speaking submission failed: Step {step_id} not found or wrong type.")
            raise ValidationError("Step not found or not a speaking exercise.")

        if step.lesson_id != session.lesson_id:
            logger.warning(f"Speaking submission failed: Step {step_id} does not belong to lesson {session.lesson_id}.")
            raise ValidationError("Step does not belong to this lesson.")

        submission = SpeechSubmission.objects.create(
            user=user,
            session=session,
            step=step,
            audio_file=audio_file,
            status='pending'
        )
        logger.info(f"Speaking submission created: ID={submission.id}, User={user.id}, Step={step.id}")
        
        return submission

    @staticmethod
    def process_evaluation(submission_id: str, mock_score: int = None):
        """
        Simulates the async evaluation process.
        Hardened with transaction locking and idempotency checks.
        """
        from .progress_service import ProgressTrackingService
        
        with transaction.atomic():
            try:
                # Use select_for_update to prevent race conditions
                submission = SpeechSubmission.objects.select_for_update().select_related(
                    'session', 'step', 'step__detail_speak_phrase'
                ).get(id=submission_id)
            except SpeechSubmission.DoesNotExist:
                logger.error(f"Async evaluation failed: Submission {submission_id} not found.")
                return

            # 1. Idempotency check: only process if pending
            if submission.status != 'pending':
                logger.info(f"Async evaluation skipped: Submission {submission_id} is already {submission.status}.")
                return
            
            if submission.session.status != 'active':
                logger.warning(f"Async evaluation failed: Session {submission.session_id} is no longer active.")
                submission.status = 'failed'
                submission.error_message = "Session is no longer active."
                submission.save()
                return

            submission.status = 'processing'
            submission.save(update_fields=['status'])

            # 2. Provider score resolution
            score = mock_score if mock_score is not None else 85 
            
            # 3. Resolve Evaluator to determine correctness
            config = StepRegistry.get('speak_phrase')
            evaluator = config.evaluator_class(submission.step.detail_speak_phrase)
            result = evaluator.evaluate({'score': score})

            # 4. Create the official StepAttempt only if it doesn't exist
            if not submission.attempt:
                attempt = StepAttempt.objects.create(
                    session=submission.session,
                    step=submission.step,
                    is_correct=result.is_correct,
                    score=result.score,
                    client_payload={"submission_id": str(submission.id)}
                )
                
                # Update Progress
                ProgressTrackingService.update_progress_after_attempt(attempt)

                # Update Submission
                submission.attempt = attempt
                submission.status = 'completed'
                submission.final_score = score
                submission.completed_at = timezone.now()
                submission.save()
                
                logger.info(f"Async evaluation completed: Submission={submission.id}, Correct={result.is_correct}, Score={score}")
            else:
                logger.info(f"Async evaluation idempotency: Submission {submission.id} already has an attempt.")
