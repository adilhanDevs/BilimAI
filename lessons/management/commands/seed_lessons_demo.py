import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from lessons.models.localization import Language, TranslationGroup, Translation
from lessons.models.course import Course, Category, Lesson, LessonVocabulary
from lessons.models.engine import ContentUnit, StepChoice, MatchPairItem, ReorderToken, Asset
from lessons.services.authoring_service import ContentAuthoringService


class Command(BaseCommand):
    help = "Seeds the database with a realistic demo course, categories, and lessons."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo data before seeding',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write("Resetting demo data...")
            Course.objects.filter(slug='english-for-kyrgyz').delete()
            Language.objects.filter(code__in=['en', 'ky', 'ru']).delete()

        self.stdout.write("Seeding languages...")
        en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        ky, _ = Language.objects.get_or_create(code='ky', defaults={'name': 'Kyrgyz'})
        ru, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Russian'})

        self.stdout.write("Seeding course...")
        course, created = Course.objects.get_or_create(
            slug='english-for-kyrgyz',
            defaults={
                'title': 'English for Beginners',
                'source_language': 'ky',
                'target_language': 'en',
                'description_ky': 'Кыргыз тилинде сүйлөгөндөр үчүн англис тилинин негиздери.',
                'cefr_min': 'A0',
                'cefr_max': 'A1',
            }
        )

        if not created:
            self.stdout.write(self.style.WARNING("Course 'english-for-kyrgyz' already exists. Skipping creation."))
            return

        # Helper to create translation groups
        def create_tg(texts_dict):
            tg = TranslationGroup.objects.create()
            for lang_code, text in texts_dict.items():
                lang = Language.objects.get(code=lang_code)
                Translation.objects.create(group=tg, language=lang, text=text)
            return tg

        # Helper to create content units
        def create_cu(unit_type, text, meaning, ky_text=None):
            tg_text = create_tg({'en': text, 'ky': ky_text or meaning})
            tg_meaning = create_tg({'ky': meaning})
            return ContentUnit.objects.create(
                unit_type=unit_type,
                text=text,
                meaning=meaning,
                text_group=tg_text,
                meaning_group=tg_meaning
            )

        # --- Category 1: Greetings ---
        cat_greetings = Category.objects.create(
            course=course,
            slug='greetings',
            title_ky='Саламдашуу',
            title_target='Greetings',
            description_ky='Адамдар менен саламдашууну жана коштошууну үйрөнүңүз.',
            icon='hand',
            sort_order=1
        )

        # Lesson 1.1: Basic Hello
        lesson_hello = Lesson.objects.create(
            category=cat_greetings,
            slug='basic-hello',
            title='Hello & Goodbye',
            description_ky='Эң негизги саламдашуу сөздөрү.',
            xp_reward=50,
            sort_order=1
        )

        # Vocabulary for Lesson 1.1
        cu_hello = create_cu('word', 'Hello', 'Салам', 'Салам')
        cu_hi = create_cu('word', 'Hi', 'Салам (бейрасмий)', 'Салам')
        cu_bye = create_cu('word', 'Goodbye', 'Жакшы калыңыз', 'Жакшы калыңыз')

        LessonVocabulary.objects.create(lesson=lesson_hello, word_or_phrase_target='Hello', translation_ky='Салам', content_unit=cu_hello, sort_order=1)
        LessonVocabulary.objects.create(lesson=lesson_hello, word_or_phrase_target='Goodbye', translation_ky='Жакшы калыңыз', content_unit=cu_bye, sort_order=2)

        # Steps for Lesson 1.1
        # Step 1: Multiple Choice
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_hello,
            step_type='multiple_choice',
            prompt_text='How do you say "Салам" in English?',
            instruction_text='Choose the correct option.',
            prompt_group=create_tg({'ky': '"Салам" англисче кандай болот?', 'en': 'How do you say "Hello" in English?'}),
            sort_order=1,
            detail_data={}
        )
        step1_detail = lesson_hello.steps.get(sort_order=1).detail
        StepChoice.objects.create(step_detail=step1_detail, text='Hello', is_correct=True, sort_order=1)
        StepChoice.objects.create(step_detail=step1_detail, text='Apple', is_correct=False, sort_order=2)
        StepChoice.objects.create(step_detail=step1_detail, text='Water', is_correct=False, sort_order=3)

        # Step 2: Fill in the Blank
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_hello,
            step_type='fill_blank',
            prompt_text='Complete the sentence',
            instruction_text='Type the missing word.',
            sort_order=2,
            detail_data={
                'sentence_template': '[[blank]], my name is John.',
                'acceptable_answers': ['Hello', 'Hi']
            }
        )

        # Step 3: Match Pairs
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_hello,
            step_type='match_pairs',
            prompt_text='Match English words with Kyrgyz translations',
            sort_order=3,
            detail_data={}
        )
        step3_detail = lesson_hello.steps.get(sort_order=3).detail
        MatchPairItem.objects.create(step_detail=step3_detail, left_text='Hello', right_text='Салам', sort_order=1)
        MatchPairItem.objects.create(step_detail=step3_detail, left_text='Goodbye', right_text='Жакшы кал', sort_order=2)
        MatchPairItem.objects.create(step_detail=step3_detail, left_text='Friend', right_text='Дос', sort_order=3)

        # --- Category 2: Food & Drinks ---
        cat_food = Category.objects.create(
            course=course,
            slug='food-drinks',
            title_ky='Тамак-аш жана суусундуктар',
            title_target='Food & Drinks',
            description_ky='Күнүмдүк тамак-аштар жана суусундуктар жөнүндө.',
            icon='utensils',
            sort_order=2
        )

        # Lesson 2.1: Basic Items
        lesson_basic_food = Lesson.objects.create(
            category=cat_food,
            slug='basic-food-items',
            title='Water and Bread',
            description_ky='Эң керектүү тамак-аштар.',
            xp_reward=60,
            sort_order=1
        )

        # Step 1: Reorder Sentence
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_basic_food,
            step_type='reorder_sentence',
            prompt_text='Translate: "Мен суу ичем"',
            instruction_text='Put the words in the correct order.',
            sort_order=1,
            detail_data={}
        )
        step4_detail = lesson_basic_food.steps.get(sort_order=1).detail
        ReorderToken.objects.create(step_detail=step4_detail, text='I', sort_order=1)
        ReorderToken.objects.create(step_detail=step4_detail, text='drink', sort_order=2)
        ReorderToken.objects.create(step_detail=step4_detail, text='water', sort_order=3)
        ReorderToken.objects.create(step_detail=step4_detail, text='apple', is_distractor=True, sort_order=4)

        # Step 2: Type Translation
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_basic_food,
            step_type='type_translation',
            prompt_text='Translate into English',
            sort_order=2,
            detail_data={
                'source_text': 'Нан',
                'acceptable_answers': ['Bread', 'A bread']
            }
        )

        # Step 3: Speak Phrase (requires Asset for reference audio in real life, but we use null here)
        ContentAuthoringService.create_lesson_step(
            lesson=lesson_basic_food,
            step_type='speak_phrase',
            prompt_text='Say this phrase clearly',
            sort_order=3,
            detail_data={
                'target_text': 'I drink water',
                'min_score_required': 70
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo course: {course.title}"))
        self.stdout.write(f"Created {Category.objects.filter(course=course).count()} categories")
        self.stdout.write(f"Created {Lesson.objects.filter(category__course=course).count()} lessons")
        self.stdout.write(f"Created {LessonStep.objects.filter(lesson__category__course=course).count()} steps")
