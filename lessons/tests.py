import uuid
import io
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count
from rest_framework.test import APITestCase
from rest_framework import status
from .models.course import Course, Category, Lesson, LessonVocabulary
from .models.engine import (
    LessonStep, StepMultipleChoice, 
    StepChoice, StepFillBlank, StepMatchPairs, MatchPairItem,
    StepReorderSentence, ReorderToken, StepTypeTranslation,
    StepSpeakPhrase, Asset, ContentUnit
)
from .models.localization import TranslationGroup, Translation, Language
from .models.progress import (
    LessonSession, StepAttempt, SpeechSubmission,
    UserLessonProgress, UserContentProgress, CourseEnrollment,
    UserCategoryProgress, ReviewItem, UserSkillProgress
)
from .evaluators import (
    MultipleChoiceEvaluator, FillBlankEvaluator, MatchPairsEvaluator,
    ReorderSentenceEvaluator, TypeTranslationEvaluator, SpeakPhraseEvaluator
)
from .services import AttemptSubmissionService
from .services.speaking_service import SpeakingEvaluationService

User = get_user_model()

class QueryOptimizationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(nickname='perf_user', email='perf@example.com', password='password')
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(slug='perf', title='Perf', source_language='en', target_language='tr')
        self.cat = Category.objects.create(course=self.course, slug='cat-p', title_ky='Cat Perf')
        self.lesson = Lesson.objects.create(category=self.cat, slug='l-p', title='L Perf')
        
        # Setup Languages
        self.lang_ky = Language.objects.create(code='ky', name='Kyrgyz')
        self.lang_en = Language.objects.create(code='en', name='English')
        
        # Setup Assets
        self.audio = Asset.objects.create(asset_type='audio', file='test.mp3')
        self.image = Asset.objects.create(asset_type='image', file='test.png')

        # Create a lesson with 6 DIFFERENT step types to stress test N+1
        # Each step will have localized content and assets
        
        # 1. Multiple Choice
        s1 = LessonStep.objects.create(lesson=self.lesson, step_type='multiple_choice', sort_order=1)
        d1 = StepMultipleChoice.objects.create(step=s1)
        tg1 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg1, language=self.lang_ky, text='MC Ky')
        cu1 = ContentUnit.objects.create(unit_type='word', text_group=tg1, primary_audio=self.audio)
        StepChoice.objects.create(step_detail=d1, content_unit=cu1, is_correct=True)
        
        # 2. Fill Blank
        s2 = LessonStep.objects.create(lesson=self.lesson, step_type='fill_blank', sort_order=2)
        tg2 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg2, language=self.lang_ky, text='FB Ky')
        cu2 = ContentUnit.objects.create(unit_type='sentence', text_group=tg2, primary_image=self.image)
        StepFillBlank.objects.create(step=s2, source_unit=cu2, sentence_template='[[blank]]', acceptable_answers=['A'])
        
        # 3. Match Pairs
        s3 = LessonStep.objects.create(lesson=self.lesson, step_type='match_pairs', sort_order=3)
        d3 = StepMatchPairs.objects.create(step=s3)
        tg3 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg3, language=self.lang_ky, text='Left Ky')
        cu3 = ContentUnit.objects.create(unit_type='word', text_group=tg3)
        MatchPairItem.objects.create(step_detail=d3, left_content_unit=cu3, right_text='Right')
        
        # 4. Reorder
        s4 = LessonStep.objects.create(lesson=self.lesson, step_type='reorder_sentence', sort_order=4)
        d4 = StepReorderSentence.objects.create(step=s4)
        tg4 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg4, language=self.lang_ky, text='Token Ky')
        cu4 = ContentUnit.objects.create(unit_type='word', text_group=tg4)
        ReorderToken.objects.create(step_detail=d4, content_unit=cu4, sort_order=1)
        
        # 5. Type Translation
        s5 = LessonStep.objects.create(lesson=self.lesson, step_type='type_translation', sort_order=5)
        tg5 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg5, language=self.lang_ky, text='Src Ky')
        cu5 = ContentUnit.objects.create(unit_type='phrase', text_group=tg5)
        StepTypeTranslation.objects.create(step=s5, source_unit=cu5, acceptable_answers=['T'])

        # 6. Speak Phrase
        s6 = LessonStep.objects.create(lesson=self.lesson, step_type='speak_phrase', sort_order=6)
        tg6 = TranslationGroup.objects.create()
        Translation.objects.create(group=tg6, language=self.lang_ky, text='Speak Ky')
        cu6 = ContentUnit.objects.create(unit_type='sentence', text_group=tg6)
        StepSpeakPhrase.objects.create(step=s6, target_unit=cu6, target_text='Speak me', reference_audio=self.audio)

        self.session = LessonSession.objects.create(user=self.user, lesson=self.lesson)
        CourseEnrollment.objects.create(user=self.user, course=self.course, is_active=True)

    def test_lesson_steps_n_plus_1_safety(self):
        """
        Verify that retrieving all steps for a complex lesson triggers a constant number of queries.
        """
        url = f'/api/lessons/{self.lesson.id}/steps/'
        
        # Current optimized count is 20 for 6 diverse step types with enrollment checks.
        with self.assertNumQueries(20):
            response = self.client.get(url, {'lang': 'ky'})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            results = response.data['results']
            self.assertEqual(len(results), 6)
            
            # Verify translation was actually used from prefetch (no extra queries during iteration)
            for step in results:
                self.assertIsNotNone(step['content'])

    def test_session_status_query_count(self):
        """
        Verify that session status endpoint is optimized.
        """
        url = f'/api/attempts/session/{self.session.id}/'
        
        # Should be exactly 1 query with the annotation and select_related
        with self.assertNumQueries(1):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['total_steps'], 6)

    def test_attempt_submission_query_safety(self):
        """
        Verify that submitting an attempt doesn't trigger N+1 queries during progress update.
        """
        step = LessonStep.objects.get(lesson=self.lesson, step_type='multiple_choice')
        detail = step.detail_multiple_choice
        choice = detail.choices.first()
        
        # Expecting around 42 queries due to comprehensive domain integration logic
        with self.assertNumQueries(42):
            AttemptSubmissionService.submit_attempt(
                self.user, str(self.session.id), str(step.id), {'selected_choice_id': choice.id}
            )


    def test_speaking_status_polling_query_count(self):
        """
        Verify that speaking submission status retrieval is optimized.
        """
        step = LessonStep.objects.get(lesson=self.lesson, step_type='speak_phrase')
        submission = SpeechSubmission.objects.create(
            user=self.user,
            session=self.session,
            step=step,
            audio_file='test.wav',
            status='pending'
        )
        
        url = f'/api/speaking/submissions/{submission.id}/'
        
        # Should be 1 query due to select_related('attempt', 'step')
        with self.assertNumQueries(1):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class DomainIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(nickname='dom_user', email='dom@example.com', password='password')
        self.course = Course.objects.create(slug='dom-c', title='Dom', source_language='en', target_language='tr')
        self.cat1 = Category.objects.create(course=self.course, slug='cat1', title_ky='Cat 1', sort_order=1)
        self.cat2 = Category.objects.create(course=self.course, slug='cat2', title_ky='Cat 2', sort_order=2, prerequisite_category=self.cat1)
        
        self.lesson = Lesson.objects.create(category=self.cat1, slug='l1', title='L1')
        self.step = LessonStep.objects.create(lesson=self.lesson, step_type='multiple_choice', xp_reward=50)
        self.detail = StepMultipleChoice.objects.create(step=self.step)
        
        self.cu = ContentUnit.objects.create(unit_type='word', text='Hello')
        StepChoice.objects.create(step_detail=self.detail, content_unit=self.cu, is_correct=True)
        
        self.session = LessonSession.objects.create(user=self.user, lesson=self.lesson)
        CourseEnrollment.objects.create(user=self.user, course=self.course, is_active=True)

    def test_vocabulary_linkage(self):
        """Verify LessonVocabulary can link to ContentUnit."""
        vocab = LessonVocabulary.objects.create(
            lesson=self.lesson, 
            word_or_phrase_target='Hello', 
            translation_ky='Салам'
        )
        vocab.content_unit = self.cu
        vocab.save()
        self.assertEqual(vocab.content_unit.text, 'Hello')

    def test_category_progress_and_unlock(self):
        """Verify category progress updates and unlocks next category upon lesson completion."""
        from .services import ProgressTrackingService
        
        # Initially cat2 is locked
        cat2_prog, _ = UserCategoryProgress.objects.get_or_create(user=self.user, category=self.cat2)
        self.assertEqual(cat2_prog.status, 'locked')
        
        # Complete the only step in the only lesson of cat1
        choice = self.detail.choices.first()
        AttemptSubmissionService.submit_attempt(
            self.user, str(self.session.id), str(self.step.id), {'selected_choice_id': str(choice.id)}
        )
        
        # Cat1 should be completed
        cat1_prog = UserCategoryProgress.objects.get(user=self.user, category=self.cat1)
        self.assertEqual(cat1_prog.status, 'completed')
        self.assertEqual(cat1_prog.progress_percent, 100)
        
        # Cat2 should now be available
        cat2_prog.refresh_from_db()
        self.assertEqual(cat2_prog.status, 'available')

    def test_skill_progress_updates(self):
        """Verify skill scores increase after attempts."""
        from .services import SkillProgressService
        
        # Initial score 0
        skill_prog, _ = UserSkillProgress.objects.get_or_create(user=self.user, course=self.course, skill='vocabulary')
        # We need to use integer 0 because F() will be used
        self.assertEqual(skill_prog.score, 0)
        
        attempt = StepAttempt.objects.create(
            session=self.session,
            step=self.step,
            is_correct=True,
            client_payload={}
        )
        SkillProgressService.update_skill_progress(attempt)
        
        skill_prog.refresh_from_db()
        self.assertTrue(skill_prog.score > 0)

    def test_review_item_sync(self):
        """Verify ReviewItem is created when mastery is low."""
        from .services import ReviewQueueService
        content_prog, _ = UserContentProgress.objects.get_or_create(
            user=self.user, content_unit=self.cu, mastery_score=50
        )
        
        ReviewQueueService.sync_review_item(content_prog)
        
        review = ReviewItem.objects.get(user=self.user, content_unit=self.cu)
        self.assertFalse(review.is_completed)
        
        # High mastery should resolve it
        content_prog.mastery_score = 90
        content_prog.save()
        ReviewQueueService.sync_review_item(content_prog)
        
        review.refresh_from_db()
        self.assertTrue(review.is_completed)


class AuthoringTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(slug='auth-c', title='Auth', source_language='en', target_language='tr')
        self.cat = Category.objects.create(course=self.course, slug='auth-cat', title_ky='Auth Cat')
        self.lesson = Lesson.objects.create(category=self.cat, slug='auth-l', title='Auth Lesson')

    def test_create_lesson_step_service(self):
        """Verify service creates both step and detail atomically."""
        from .services import ContentAuthoringService
        step = ContentAuthoringService.create_lesson_step(
            lesson=self.lesson,
            step_type='multiple_choice',
            sort_order=1
        )
        self.assertEqual(step.step_type, 'multiple_choice')
        self.assertIsNotNone(step.detail_multiple_choice)

    def test_clone_lesson_service(self):
        """Verify deep cloning of lessons works."""
        from .services import ContentAuthoringService
        # Setup original
        s1 = ContentAuthoringService.create_lesson_step(self.lesson, 'multiple_choice', sort_order=1)
        StepChoice.objects.create(step_detail=s1.detail_multiple_choice, text='C1')
        
        cloned = ContentAuthoringService.clone_lesson(self.lesson, new_title="Cloned")
        
        self.assertEqual(cloned.title, "Cloned")
        self.assertEqual(cloned.steps.count(), 1)
        new_step = cloned.steps.first()
        self.assertEqual(new_step.step_type, 'multiple_choice')
        self.assertEqual(new_step.detail_multiple_choice.choices.count(), 1)
        self.assertNotEqual(new_step.id, s1.id)

    def test_lesson_step_validation(self):
        """Verify clean() prevents unsupported step types."""
        from django.core.exceptions import ValidationError
        step = LessonStep(lesson=self.lesson, step_type='invalid_type')
        with self.assertRaises(ValidationError):
            step.full_clean()

    def test_fill_blank_validation(self):
        """Verify integrity of fill_blank details."""
        from django.core.exceptions import ValidationError
        step = LessonStep.objects.create(lesson=self.lesson, step_type='fill_blank')
        detail = StepFillBlank(
            step=step, 
            sentence_template="No placeholders", 
            acceptable_answers=["A"]
        )
        with self.assertRaises(ValidationError):
            detail.full_clean()


class EvaluatorLogicTests(TestCase):
    def test_reorder_sentence_logic_uses_prefetched(self):
        # Setup similar to QueryOptimizationTests but for unit testing evaluator
        course = Course.objects.create(slug='e1', title='E1', source_language='en', target_language='tr')
        cat = Category.objects.create(course=course, slug='c1', title_ky='C1')
        lesson = Lesson.objects.create(category=cat, slug='l1', title='L1')
        step = LessonStep.objects.create(lesson=lesson, step_type='reorder_sentence')
        detail = StepReorderSentence.objects.create(step=step)
        t1 = ReorderToken.objects.create(step_detail=detail, text='1', sort_order=1)
        t2 = ReorderToken.objects.create(step_detail=detail, text='2', sort_order=2)
        
        # Simulate prefetching
        step_opt = LessonStep.objects.with_details().get(id=step.id)
        evaluator = ReorderSentenceEvaluator(step_opt.detail_reorder_sentence)
        
        # This should NOT trigger queries if implemented correctly with Python filtering
        with self.assertNumQueries(0):
            res = evaluator.evaluate({'token_ids': [t1.id, t2.id]})
            self.assertTrue(res.is_correct)

    def test_multiple_choice_logic_uses_prefetched(self):
        course = Course.objects.create(slug='e2', title='E2', source_language='en', target_language='tr')
        cat = Category.objects.create(course=course, slug='c2', title_ky='C2')
        lesson = Lesson.objects.create(category=cat, slug='l2', title='L2')
        step = LessonStep.objects.create(lesson=lesson, step_type='multiple_choice')
        detail = StepMultipleChoice.objects.create(step=step)
        c1 = StepChoice.objects.create(step_detail=detail, text='Yes', is_correct=True)
        
        step_opt = LessonStep.objects.with_details().get(id=step.id)
        evaluator = MultipleChoiceEvaluator(step_opt.detail_multiple_choice)
        
        with self.assertNumQueries(0):
            res = evaluator.evaluate({'selected_choice_id': c1.id})
            self.assertTrue(res.is_correct)
