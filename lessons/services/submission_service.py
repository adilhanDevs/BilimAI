import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError
from django.db import transaction
from ..models.progress import LessonSession, StepAttempt
from ..models.engine import LessonStep
from ..registry import StepRegistry
from ..evaluators import EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class SubmissionResult:
    is_correct: bool
    score: int
    xp_awarded: int
    feedback: Dict[str, Any] = field(default_factory=dict)


class AttemptSubmissionService:
    @staticmethod
    def submit_attempt(user, session_id: str, step_id: str, payload: Dict[str, Any]) -> SubmissionResult:
        """
        Coordinates the submission of a lesson step attempt.
        """
        # 1. Load session and step
        from django.db.models import Count
        try:
            session = LessonSession.objects.annotate(
                total_steps_count=Count('lesson__steps')
            ).select_related('lesson').get(id=session_id)
        except (LessonSession.DoesNotExist, ValidationError):
            logger.warning(f"Attempt submit failed: Session {session_id} not found.")
            raise ValidationError("Session not found.")

        # Ownership Check
        if session.user_id != user.id:
            logger.error(f"Unauthorized attempt access: User {user.id} tried to access session {session_id} owned by user {session.user_id}.")
            raise ValidationError("You do not have permission to access this session.")

        if session.status != 'active':
            logger.info(f"Attempt submit rejected: Session {session_id} is already {session.status}.")
            raise ValidationError("Session is no longer active.")

        # Enrollment Check
        from .course_enrollment_service import CourseEnrollmentService
        if not CourseEnrollmentService.is_enrolled(session.user, session.lesson.category.course):
            logger.warning(f"Attempt submit rejected: User {user.id} not enrolled in course {session.lesson.category.course_id}.")
            raise ValidationError("User is not enrolled in this course.")

        try:
            # Load step with its specific detail model
            step = LessonStep.objects.with_details().get(id=step_id)
        except (LessonStep.DoesNotExist, ValidationError):
            logger.warning(f"Attempt submit failed: Step {step_id} not found.")
            raise ValidationError("Step not found.")

        # 2. Validate step-session relation
        if step.lesson_id != session.lesson_id:
            logger.warning(f"Attempt submit failed: Step {step_id} does not belong to session {session_id} lesson.")
            raise ValidationError("This step does not belong to the current session's lesson.")

        # 3. Resolve Evaluator
        config = StepRegistry.get(step.step_type)
        if not config or not config.evaluator_class:
            logger.error(f"Config error: No evaluator for {step.step_type}")
            raise ValidationError(f"No evaluator registered for step type: {step.step_type}")

        detail_obj = getattr(step, config.relation_name, None)
        if not detail_obj:
            logger.error(f"Data error: Step detail missing for {step.id} ({step.step_type})")
            raise ValidationError(f"Step detail missing for {step.step_type}")

        evaluator = config.evaluator_class(detail_obj)

        # 4. Evaluate
        evaluation = evaluator.evaluate(payload)

        # 5. Persist Attempt and Update Progress
        from .progress_service import ProgressTrackingService
        with transaction.atomic():
            attempt = StepAttempt.objects.create(
                session=session,
                step=step,
                is_correct=evaluation.is_correct,
                score=evaluation.score,
                client_payload=payload
            )
            ProgressTrackingService.update_progress_after_attempt(attempt)

        logger.info(f"Attempt processed: User={user.id}, Step={step.id}, Correct={evaluation.is_correct}")

        # 6. Prepare Final Result
        return SubmissionResult(
            is_correct=evaluation.is_correct,
            score=evaluation.score,
            xp_awarded=step.xp_reward if evaluation.is_correct else 0,
            feedback=evaluation.feedback or {}
        )
