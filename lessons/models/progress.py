import uuid
from django.db import models
from django.conf import settings
from .course import Lesson, LessonVocabulary, Course, Category
from .engine import LessonStep, ContentUnit


class LessonSession(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_sessions')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='sessions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Gamification state
    hearts_remaining = models.IntegerField(default=5)
    mistakes_count = models.IntegerField(default=0)
    xp_earned = models.IntegerField(default=0)
    completed_steps_count = models.IntegerField(default=0)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.id} - {self.user.nickname} - {self.lesson.title}"

    @property
    def is_failed(self):
        return self.hearts_remaining <= 0

    @property
    def total_steps(self):
        if hasattr(self, 'total_steps_count'):
            return self.total_steps_count
        return self.lesson.steps.count()


class StepAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LessonSession, on_delete=models.CASCADE, related_name='attempts')
    step = models.ForeignKey(LessonStep, on_delete=models.CASCADE, related_name='attempts')
    is_correct = models.BooleanField()
    score = models.IntegerField(default=0)
    client_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class SpeechSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LessonSession, on_delete=models.CASCADE, related_name='speech_submissions')
    step = models.ForeignKey(LessonStep, on_delete=models.CASCADE, related_name='speech_submissions')
    attempt = models.OneToOneField(StepAttempt, on_delete=models.SET_NULL, null=True, blank=True, related_name='speech_submission')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='speech_submissions')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    audio_file = models.FileField(upload_to='speech_submissions/%Y/%m/%d/')
    provider = models.CharField(max_length=50, blank=True)
    external_job_id = models.CharField(max_length=255, blank=True, null=True)
    
    final_score = models.IntegerField(null=True, blank=True)
    raw_result = models.JSONField(null=True, blank=True)
    feedback_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class UserLessonProgress(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('mastered', 'Mastered'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    
    best_score = models.IntegerField(default=0)
    total_sessions = models.IntegerField(default=0)
    total_attempts = models.IntegerField(default=0)
    total_correct_attempts = models.IntegerField(default=0)
    total_xp_earned = models.IntegerField(default=0)
    
    last_session = models.ForeignKey(LessonSession, on_delete=models.SET_NULL, null=True, blank=True)
    
    first_started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lesson')


class UserContentProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='content_progress')
    content_unit = models.ForeignKey(ContentUnit, on_delete=models.CASCADE, related_name='user_progress')
    
    exposure_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    incorrect_count = models.IntegerField(default=0)
    
    last_seen_at = models.DateTimeField(auto_now=True)
    mastery_score = models.IntegerField(default=0)
    next_review_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'content_unit')


class CourseEnrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'course')


class UserCategoryProgress(models.Model):
    STATUS_CHOICES = [
        ('locked', 'Locked'),
        ('available', 'Available'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='category_progress')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='user_progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='locked')
    progress_percent = models.IntegerField(default=0)
    completed_lessons = models.IntegerField(default=0)
    total_lessons = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'category')


class ReviewItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_items')
    content_unit = models.ForeignKey(ContentUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='review_items')
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True)
    vocabulary = models.ForeignKey(LessonVocabulary, on_delete=models.SET_NULL, null=True, blank=True)
    item_type = models.CharField(max_length=50)
    target_text = models.TextField()
    translation_ky = models.TextField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True)
    strength = models.IntegerField(default=0)
    mistake_count = models.IntegerField(default=0)
    correct_streak = models.IntegerField(default=0)
    last_reviewed_at = models.DateTimeField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class UserSkillProgress(models.Model):
    SKILLS = [
        ('reading', 'Reading'),
        ('writing', 'Writing'),
        ('listening', 'Listening'),
        ('speaking', 'Speaking'),
        ('vocabulary', 'Vocabulary'),
        ('grammar', 'Grammar'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_progress')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    skill = models.CharField(max_length=20, choices=SKILLS)
    score = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'course', 'skill')
