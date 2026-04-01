from django.utils import timezone
from django.db.models import Count, Q
from ..models.course import Lesson, Category
from ..models.progress import UserLessonProgress, UserCategoryProgress


class CategoryProgressService:
    @staticmethod
    def update_category_progress(user, category: Category):
        """
        Recalculates completion percentage and status for a category.
        Also handles unlocking of dependent categories.
        """
        # 1. Get stats
        total_lessons = Lesson.objects.filter(category=category, is_published=True).count()
        if total_lessons == 0:
            return

        completed_lessons = UserLessonProgress.objects.filter(
            user=user, 
            lesson__category=category, 
            status='completed'
        ).count()

        progress_percent = int((completed_lessons / total_lessons) * 100)

        # 2. Update/Create category progress
        cat_progress, _ = UserCategoryProgress.objects.get_or_create(
            user=user, category=category
        )
        
        cat_progress.total_lessons = total_lessons
        cat_progress.completed_lessons = completed_lessons
        cat_progress.progress_percent = progress_percent
        
        # Update status
        if completed_lessons == 0:
            if cat_progress.status == 'locked':
                # Check if it should be available
                if CategoryProgressService.is_category_unlocked(user, category):
                    cat_progress.status = 'available'
            else:
                cat_progress.status = 'available'
        elif completed_lessons < total_lessons:
            cat_progress.status = 'in_progress'
        else:
            cat_progress.status = 'completed'
            # Trigger unlock check for next categories
            CategoryProgressService.trigger_next_unlocks(user, category)

        cat_progress.save()

    @staticmethod
    def is_category_unlocked(user, category: Category) -> bool:
        """
        Checks if prerequisite category is completed.
        """
        if not category.prerequisite_category:
            return True
        
        return UserCategoryProgress.objects.filter(
            user=user, 
            category=category.prerequisite_category, 
            status='completed'
        ).exists()

    @staticmethod
    def trigger_next_unlocks(user, completed_category: Category):
        """
        Unlocks categories that depend on the one just completed.
        """
        next_cats = Category.objects.filter(prerequisite_category=completed_category)
        for cat in next_cats:
            cat_progress, _ = UserCategoryProgress.objects.get_or_create(
                user=user, category=cat
            )
            if cat_progress.status == 'locked':
                cat_progress.status = 'available'
                cat_progress.save()
