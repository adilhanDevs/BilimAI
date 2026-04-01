import uuid
import io
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from .models.course import Course, Category, Lesson
from .models.engine import (
    LessonStep, StepMultipleChoice, StepChoice, Asset, ContentUnit
)
from .models.progress import (
    LessonSession, StepAttempt, SpeechSubmission,
    UserLessonProgress, UserContentProgress, CourseEnrollment,
    UserCategoryProgress, UserSkillProgress, ReviewItem
)
from .services import AttemptSubmissionService
from .services.speaking_service import SpeakingEvaluationService

User = get_user_model()

class ProductionConfidenceTests(APITestCase):
    """
    High-stress integration tests covering invariants, idempotency, and security.
    """
    def setUp(self):
        self.user = User.objects.create_user(nickname='pro_user', email='pro@example.com', password='password')
        self.other_user = User.objects.create_user(nickname='other_user', email='other@example.com', password='password')
        
        self.course = Course.objects.create(slug='pro-c', title='Pro Course', source_language='en', target_language='tr')
        self.cat = Category.objects.create(course=self.course, slug='pro-cat', title_ky='Pro Cat')
        self.lesson = Lesson.objects.create(category=self.cat, slug='pro-l', title='Pro Lesson')
        
        # Create TWO steps to prevent premature session completion
        self.s1 = LessonStep.objects.create(lesson=self.lesson, step_type='multiple_choice', sort_order=1, xp_reward=10)
        self.d1 = StepMultipleChoice.objects.create(step=self.s1)
        self.cu = ContentUnit.objects.create(unit_type='word', text='Test')
        self.c1 = StepChoice.objects.create(step_detail=self.d1, content_unit=self.cu, is_correct=True)
        
        self.s2 = LessonStep.objects.create(lesson=self.lesson, step_type='multiple_choice', sort_order=2, xp_reward=10)
        self.d2 = StepMultipleChoice.objects.create(step=self.s2)
        self.c2 = StepChoice.objects.create(step_detail=self.d2, text='C2', is_correct=True)

        self.session = LessonSession.objects.create(user=self.user, lesson=self.lesson)
        CourseEnrollment.objects.create(user=self.user, course=self.course, is_active=True)
        self.client.force_authenticate(user=self.user)

    def test_attempt_idempotency(self):
        """Verify that submitting the same payload twice doesn't double XP or progress."""
        payload = {'selected_choice_id': str(self.c1.id)}
        
        # 1st attempt
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s1.id), payload)
        self.session.refresh_from_db()
        self.assertEqual(self.session.xp_earned, 10)
        self.assertEqual(self.session.completed_steps_count, 1)
        
        # 2nd attempt (same step)
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s1.id), payload)
        self.session.refresh_from_db()
        self.assertEqual(self.session.xp_earned, 10, "XP should not double count")
        self.assertEqual(self.session.completed_steps_count, 1, "Completed steps should not double count")
        
        # Verify StepAttempt count
        self.assertEqual(StepAttempt.objects.filter(session=self.session, step=self.s1).count(), 2)

    def test_cross_user_session_protection(self):
        """Verify user A cannot submit attempts for user B's session."""
        self.client.force_authenticate(user=self.other_user)
        url = '/api/attempts/submit/'
        data = {
            'session_id': str(self.session.id),
            'step_id': str(self.s1.id),
            'payload': {'selected_choice_id': str(self.c1.id)}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("permission", response.data['detail'])

    def test_unenrolled_user_rejection(self):
        """Verify user not enrolled in course cannot submit attempts."""
        new_course = Course.objects.create(slug='secret', title='Secret')
        new_cat = Category.objects.create(course=new_course, slug='secret-cat')
        new_lesson = Lesson.objects.create(category=new_cat, slug='secret-l')
        new_session = LessonSession.objects.create(user=self.user, lesson=new_lesson)
        
        # User is NOT enrolled in new_course
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            AttemptSubmissionService.submit_attempt(self.user, str(new_session.id), str(self.s1.id), {})

    def test_speaking_processing_idempotency(self):
        """Verify async processing of the same submission doesn't double side effects."""
        s_speak = LessonStep.objects.create(lesson=self.lesson, step_type='speak_phrase', sort_order=3)
        from .models.engine import StepSpeakPhrase
        StepSpeakPhrase.objects.create(step=s_speak, target_text="Hello")
        
        audio = SimpleUploadedFile("test.wav", b"fake audio content", content_type="audio/wav")
        submission = SpeakingEvaluationService.create_submission(
            self.user, str(self.session.id), str(s_speak.id), audio
        )
        
        SpeakingEvaluationService.process_evaluation(str(submission.id), mock_score=90)
        self.session.refresh_from_db()
        xp_after_1 = self.session.xp_earned
        
        SpeakingEvaluationService.process_evaluation(str(submission.id), mock_score=90)
        self.session.refresh_from_db()
        
        self.assertEqual(self.session.xp_earned, xp_after_1, "XP should not double count on speaking retry")
        self.assertEqual(StepAttempt.objects.filter(session=self.session, step=s_speak).count(), 1)

    def test_content_mastery_and_review_invariants(self):
        """Verify correct mastery updates and review item lifecycle."""
        prog, _ = UserContentProgress.objects.get_or_create(user=self.user, content_unit=self.cu)
        self.assertEqual(prog.mastery_score, 0)
        
        # 1. Correct attempt -> mastery up
        payload = {'selected_choice_id': str(self.c1.id)}
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s1.id), payload)
        
        prog.refresh_from_db()
        self.assertEqual(prog.mastery_score, 10)
        
        # 2. Wrong attempt -> mastery down
        c_wrong = StepChoice.objects.create(step_detail=self.d1, text='Wrong', content_unit=self.cu, is_correct=False)
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s1.id), {'selected_choice_id': str(c_wrong.id)})
        
        prog.refresh_from_db()
        self.assertEqual(prog.mastery_score, 5) # 10 - 5
        self.assertTrue(ReviewItem.objects.filter(user=self.user, content_unit=self.cu, is_completed=False).exists())

    def test_category_unlock_invariant(self):
        """Verify category unlock happens correctly."""
        cat2 = Category.objects.create(course=self.course, slug='cat2', prerequisite_category=self.cat)
        cat2_prog, _ = UserCategoryProgress.objects.get_or_create(user=self.user, category=cat2)
        self.assertEqual(cat2_prog.status, 'locked')
        
        # Complete all steps (s1 and s2)
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s1.id), {'selected_choice_id': str(self.c1.id)})
        AttemptSubmissionService.submit_attempt(self.user, str(self.session.id), str(self.s2.id), {'selected_choice_id': str(self.c2.id)})
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'completed')
        
        cat2_prog.refresh_from_db()
        self.assertEqual(cat2_prog.status, 'available')

    def test_mixed_step_query_count_stability(self):
        """Verify retrieving mixed steps stays optimized."""
        url = f'/api/lessons/{self.lesson.id}/steps/'
        # Regression lock: 6 queries for this lesson structure
        with self.assertNumQueries(6):
            response = self.client.get(url, {'lang': 'ky'})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_speaking_async_failure_path(self):
        """Verify that failures in speaking processing don't break the session."""
        s_speak = LessonStep.objects.create(lesson=self.lesson, step_type='speak_phrase', sort_order=3)
        from .models.engine import StepSpeakPhrase
        StepSpeakPhrase.objects.create(step=s_speak, target_text="Fail me")
        
        audio = SimpleUploadedFile("fail.wav", b"bad audio content", content_type="audio/wav")
        submission = SpeakingEvaluationService.create_submission(
            self.user, str(self.session.id), str(s_speak.id), audio
        )
        
        SpeakingEvaluationService.process_evaluation(str(submission.id), mock_score=0)
        
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'completed')
        self.assertEqual(submission.final_score, 0)
        
        attempt = submission.attempt
        self.assertFalse(attempt.is_correct)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.hearts_remaining, 4, "Failure should consume a heart")
