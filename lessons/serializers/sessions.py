from rest_framework import serializers
from ..models.progress import (
    LessonSession, StepAttempt, SpeechSubmission, UserLessonProgress,Lesson,
    ReviewItem, UserCategoryProgress, UserSkillProgress, CourseEnrollment
)
from ..models.engine import LessonStep
from ..utils import get_translation


class LessonSummarySerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'slug', 'sort_order', 'xp_reward', 'status']

    def get_status(self, obj):
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return 'not_started'
        progress = obj.user_progress.filter(user=user).first()
        return progress.status if progress else 'not_started'


class SessionStatusSerializer(serializers.ModelSerializer):
    is_failed = serializers.BooleanField(read_only=True)
    progress_percent = serializers.SerializerMethodField()
    total_steps = serializers.SerializerMethodField()

    class Meta:
        model = LessonSession
        fields = [
            'id', 'status', 'hearts_remaining', 'mistakes_count', 
            'xp_earned', 'completed_steps_count', 'total_steps',
            'progress_percent', 'is_failed'
        ]

    def get_total_steps(self, obj):
        return obj.total_steps

    def get_progress_percent(self, obj):
        total = self.get_total_steps(obj)
        if total == 0:
            return 0
        return int((obj.completed_steps_count / total) * 100)


class LessonProgressSerializer(serializers.ModelSerializer):
    last_session = SessionStatusSerializer(read_only=True)

    class Meta:
        model = UserLessonProgress
        fields = ['status', 'best_score', 'total_xp_earned', 'total_sessions', 'completed_at', 'last_activity_at', 'last_session']


class SpeechSubmissionRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    step_id = serializers.UUIDField()
    audio_file = serializers.FileField()

    def validate(self, data):
        # Local import to avoid circular dependency
        from ..models.engine import LessonStep
        try:
            step = LessonStep.objects.get(id=data['step_id'])
            if step.step_type != 'speak_phrase':
                raise serializers.ValidationError("Only 'speak_phrase' steps support audio submissions.")
        except LessonStep.DoesNotExist:
            raise serializers.ValidationError("Step not found.")
        return data


class SpeechSubmissionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechSubmission
        fields = ['id', 'status', 'final_score', 'retry_count', 'created_at']


class SpeechSubmissionStatusSerializer(serializers.ModelSerializer):
    """Flattened and consistent status for speaking exercises."""
    is_correct = serializers.BooleanField(source='attempt.is_correct', read_only=True)
    score = serializers.IntegerField(source='attempt.score', read_only=True)
    xp_awarded = serializers.SerializerMethodField()
    feedback = serializers.JSONField(source='feedback_payload', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)

    class Meta:
        model = SpeechSubmission
        fields = [
            'id', 'status', 'is_correct', 'score', 'xp_awarded', 
            'feedback', 'attempt_id', 'error_message', 'created_at'
        ]

    def get_xp_awarded(self, obj):
        if obj.attempt and obj.attempt.is_correct:
            return obj.step.xp_reward
        return 0


class ReviewItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewItem
        fields = ['id', 'item_type', 'target_text', 'translation_ky', 'due_at', 'strength', 'is_completed']


class SkillProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSkillProgress
        fields = ['skill', 'score', 'level', 'updated_at']


class UserCategoryProgressSerializer(serializers.ModelSerializer):
    category_title = serializers.CharField(source='category.title_ky', read_only=True)
    lessons = serializers.SerializerMethodField()
    
    class Meta:
        model = UserCategoryProgress
        fields = ['category_id', 'category_title', 'status', 'progress_percent', 'completed_lessons', 'total_lessons', 'lessons']

    def get_lessons(self, obj):
        # We need the lessons belonging to this category
        lessons = obj.category.lessons.filter(is_published=True).order_by('sort_order')
        return LessonSummarySerializer(lessons, many=True, context=self.context).data


class CourseSummarySerializer(serializers.ModelSerializer):
    """Overall summary of a user's progress in a course."""
    categories = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    enrolled_at = serializers.DateTimeField(source='started_at', read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = ['course_id', 'is_active', 'enrolled_at', 'categories', 'skills']

    def get_categories(self, obj):
        from ..models.progress import UserCategoryProgress
        qs = UserCategoryProgress.objects.filter(user=obj.user, category__course=obj.course).select_related('category')
        return UserCategoryProgressSerializer(qs, many=True).data

    def get_skills(self, obj):
        from ..models.progress import UserSkillProgress
        qs = UserSkillProgress.objects.filter(user=obj.user, course=obj.course)
        return SkillProgressSerializer(qs, many=True).data


class AttemptRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    step_id = serializers.UUIDField()
    payload = serializers.JSONField()


class AttemptResponseSerializer(serializers.Serializer):
    """Standard result structure for attempt submission."""
    is_correct = serializers.BooleanField()
    score = serializers.IntegerField()
    xp_awarded = serializers.IntegerField()
    feedback = serializers.JSONField(required=False, allow_null=True)
    # Convenience snapshot of the session after the attempt
    session = SessionStatusSerializer(read_only=True)
