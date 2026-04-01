import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from .models.course import Course, Category, Lesson
from .models.engine import LessonStep, StepMultipleChoice, StepChoice, ContentUnit
from .models.progress import LessonSession, CourseEnrollment, StepAttempt, ReviewItem

User = get_user_model()

class ApiContractTests(APITestCase):
    """
    Ensures that API response shapes match the frontend team's expectations.
    """
    def setUp(self):
        self.user = User.objects.create_user(nickname='contract_user', email='contract@example.com', password='password')
        self.course = Course.objects.create(slug='c1', title='C1')
        self.cat = Category.objects.create(course=self.course, slug='cat1', title_ky='Cat 1')
        self.lesson = Lesson.objects.create(category=self.cat, slug='l1', title='L1')
        
        # Enrollment is required
        CourseEnrollment.objects.create(user=self.user, course=self.course, is_active=True)
        
        # Step setup
        self.s1 = LessonStep.objects.create(lesson=self.lesson, step_type='multiple_choice', sort_order=1, xp_reward=10)
        self.d1 = StepMultipleChoice.objects.create(step=self.s1)
        self.cu = ContentUnit.objects.create(unit_type='word', text='Hello')
        self.c1 = StepChoice.objects.create(step_detail=self.d1, content_unit=self.cu, is_correct=True)
        
        self.session = LessonSession.objects.create(user=self.user, lesson=self.lesson)
        self.client.force_authenticate(user=self.user)

    def test_lesson_step_contract(self):
        url = f'/api/lessons/{self.lesson.id}/steps/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        self.assertTrue(len(results) > 0)
        step = results[0]
        
        # Check for explicitly named text fields
        self.assertIn('prompt_text', step)
        self.assertIn('instruction_text', step)
        self.assertIn('content', step)
        self.assertIn('xp_reward', step)

    def test_attempt_submission_contract(self):
        url = '/api/attempts/submit/'
        data = {
            'session_id': str(self.session.id),
            'step_id': str(self.s1.id),
            'payload': {'selected_choice_id': self.c1.id}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify flattened attempt results
        self.assertIn('is_correct', response.data)
        self.assertIn('score', response.data)
        self.assertIn('xp_awarded', response.data)
        
        # Verify session snapshot existence
        self.assertIn('session', response.data)
        session_data = response.data['session']
        self.assertIn('hearts_remaining', session_data)
        self.assertIn('xp_earned', session_data)

    def test_user_progress_summary_contract(self):
        url = '/api/progress/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should be a list of enrolled courses
        self.assertTrue(isinstance(response.data['results'], list))
        course_sum = response.data['results'][0]
        self.assertIn('course_id', course_sum)
        self.assertIn('categories', course_sum)
        self.assertIn('skills', course_sum)

    def test_review_queue_contract(self):
        ReviewItem.objects.create(
            user=self.user,
            item_type='manual',
            target_text='Review me',
            is_completed=False
        )
        url = '/api/reviews/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        self.assertTrue(len(results) > 0)
        item = results[0]
        self.assertIn('target_text', item)
        self.assertIn('due_at', item)
        self.assertIn('strength', item)
