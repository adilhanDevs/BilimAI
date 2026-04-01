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
    def link_vocabulary_to_unit(vocabulary: LessonVocabulary, content_unit_id: str):
        """
        Bridges LessonVocabulary with a ContentUnit.
        """
        vocabulary.content_unit_id = content_unit_id
        vocabulary.save(update_fields=['content_unit'])
