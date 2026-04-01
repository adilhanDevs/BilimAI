from django.db.models import F
from ..models.progress import UserSkillProgress, StepAttempt
from ..registry import StepRegistry


class SkillProgressService:
    @staticmethod
    def update_skill_progress(attempt: StepAttempt):
        """
        Increments skill scores based on step type contributions.
        """
        user = attempt.session.user
        course = attempt.session.lesson.category.course
        step = attempt.step
        
        # 1. Get contributions from registry
        config = StepRegistry.get(step.step_type)
        if not config or not config.skill_contributions:
            return

        # 2. Update each skill
        for skill_code in config.skill_contributions:
            skill_progress, created = UserSkillProgress.objects.get_or_create(
                user=user, 
                course=course, 
                skill=skill_code
            )
            
            # Simple contribution: +1 for any attempt, +2 for correct
            increment = 2 if attempt.is_correct else 1
            skill_progress.score = F('score') + increment
            
            # Simple level up logic: every 100 points
            # (In production this would be more complex)
            # Note: since we use F() expressions, we'd need to refresh or handle level separately
            # For this audit, we'll keep it simple
            skill_progress.save()
            
            # Refresh to handle level up logic if needed
            skill_progress.refresh_from_db()
            new_level = (skill_progress.score // 100) + 1
            if new_level > skill_progress.level:
                skill_progress.level = new_level
                skill_progress.save(update_fields=['level'])
