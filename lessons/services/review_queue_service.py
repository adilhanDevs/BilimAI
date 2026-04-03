from datetime import timedelta
from django.utils import timezone
from ..models.progress import UserContentProgress, ReviewItem
from ..models.course import LessonVocabulary


class ReviewQueueService:
    @staticmethod
    def sync_review_item(content_progress: UserContentProgress):
        """
        Ensures a ReviewItem exists if mastery is low, 
        or updates/resolves it if mastery is high.
        """
        user = content_progress.user
        unit = content_progress.content_unit
        
        # 1. Decide if review is needed
        # Threshold: if mastery < 80 or if mistakes are high
        needs_review = content_progress.mastery_score < 80
        
        if needs_review:
            # Try to find existing active review item
            review_item, created = ReviewItem.objects.get_or_create(
                user=user,
                content_unit=unit,
                defaults={
                    'item_type': 'content_unit',
                    'target_text': unit.text or str(unit.id),
                    'due_at': content_progress.next_review_at or timezone.now()
                }
            )
            
            if not created:
                # Update existing
                review_item.due_at = content_progress.next_review_at or timezone.now()
                review_item.strength = content_progress.mastery_score
                review_item.is_completed = False
                review_item.save()
        else:
            # Mastery is high, resolve existing item if any
            ReviewItem.objects.filter(user=user, content_unit=unit).update(
                is_completed=True,
                strength=content_progress.mastery_score
            )

    @staticmethod
    def resolve_review_item(review_item: ReviewItem):
        """
        Implements SRS-lite logic for a successful review.
        """
        now = timezone.now()
        review_item.correct_streak += 1
        review_item.last_reviewed_at = now
        
        # SRS-lite Intervals: 1 day, 3 days, 7 days, 14 days...
        if review_item.correct_streak == 1:
            interval = timedelta(days=1)
        elif review_item.correct_streak == 2:
            interval = timedelta(days=3)
        elif review_item.correct_streak == 3:
            interval = timedelta(days=7)
        else:
            interval = timedelta(days=14)
            
        review_item.due_at = now + interval
        
        # If streak is high enough (e.g. 4), we could mark as completed
        # but for now let's just keep it in the loop with long intervals.
        if review_item.correct_streak >= 4:
            review_item.is_completed = True
            
        review_item.save()

    @staticmethod
    def record_mistake(review_item: ReviewItem):
        """
        Handles a mistake during review: reset streak and schedule soon.
        """
        review_item.correct_streak = 0
        review_item.mistake_count += 1
        review_item.due_at = timezone.now() + timedelta(hours=4)
        review_item.save()

    @staticmethod
    def link_vocabulary_to_unit(vocabulary: LessonVocabulary, content_unit_id: str):
        """
        Bridges LessonVocabulary with a ContentUnit.
        """
        vocabulary.content_unit_id = content_unit_id
        vocabulary.save(update_fields=['content_unit'])
