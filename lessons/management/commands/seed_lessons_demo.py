import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from lessons.models.localization import Language, TranslationGroup, Translation
from lessons.models.course import Course, Category, Lesson, LessonVocabulary
from lessons.models.engine import (
    ContentUnit, StepChoice, MatchPairItem, ReorderToken, LessonStep
)
from lessons.services.authoring_service import ContentAuthoringService


class Command(BaseCommand):
    help = "Seeds the database with rich demo courses: English-Kyrgyz and Russian-Kyrgyz"

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo data before seeding',
        )
        parser.add_argument(
            '--with-user',
            action='store_true',
            help='Create a demo user and enroll them',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING("Resetting demo data..."))
            Course.objects.filter(slug__in=['english-for-kyrgyz', 'russian-for-kyrgyz']).delete()
            Language.objects.filter(code__in=['en', 'ky', 'ru']).delete()

        # ==================== LANGUAGES ====================
        self.stdout.write("Seeding languages...")
        en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        ky, _ = Language.objects.get_or_create(code='ky', defaults={'name': 'Kyrgyz'})
        ru, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Russian'})

        # ==================== HELPER FUNCTIONS ====================
        def create_tg(texts_dict: dict):
            """Создаёт TranslationGroup с переводами"""
            tg = TranslationGroup.objects.create()
            for lang_code, text in texts_dict.items():
                lang = Language.objects.get(code=lang_code)
                Translation.objects.create(group=tg, language=lang, text=text)
            return tg

        def create_cu(unit_type: str, text_en: str, meaning_ky: str, ky_text: str = None):
            """Создаёт ContentUnit"""
            tg_text = create_tg({'en': text_en, 'ky': ky_text or meaning_ky})
            tg_meaning = create_tg({'ky': meaning_ky})
            return ContentUnit.objects.create(
                unit_type=unit_type,
                text=text_en,
                meaning=meaning_ky,
                text_group=tg_text,
                meaning_group=tg_meaning
            )

        # ==================== ENGLISH FOR KYRGYZ ====================
        self.stdout.write("Seeding 'English for Kyrgyz' course...")
        course_en, created_en = Course.objects.get_or_create(
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

        if created_en:
            self._seed_english_course(course_en, create_tg, create_cu)
        else:
            self.stdout.write(self.style.WARNING("Course 'english-for-kyrgyz' already exists. Skipping creation."))

        # ==================== RUSSIAN FOR KYRGYZ ====================
        self.stdout.write("Seeding 'Russian for Kyrgyz' course...")
        course_ru, created_ru = Course.objects.get_or_create(
            slug='russian-for-kyrgyz',
            defaults={
                'title': 'Русский для кыргызов',
                'source_language': 'ky',
                'target_language': 'ru',
                'description_ky': 'Кыргыз тилинде сүйлөгөндөр үчүн орус тилинин негиздери.',
                'cefr_min': 'A0',
                'cefr_max': 'A1',
            }
        )

        if created_ru:
            self._seed_russian_course(course_ru, create_tg, create_cu)
        else:
            self.stdout.write(self.style.WARNING("Course 'russian-for-kyrgyz' already exists. Skipping creation."))

        # ==================== DEMO USER ====================
        if options.get('with_user'):
            self._create_demo_user(course_en, course_ru)

        # Final stats
        self.stdout.write(self.style.SUCCESS("\n=== Seeding completed successfully! ==="))
        self.stdout.write(f"English course lessons: {Lesson.objects.filter(category__course=course_en).count()}")
        self.stdout.write(f"Russian course lessons: {Lesson.objects.filter(category__course=course_ru).count()}")
        self.stdout.write(f"Total steps created: {LessonStep.objects.count()}")

    # ====================== ENGLISH COURSE ======================
    def _seed_english_course(self, course, create_tg, create_cu):
        # ------------------- Category: Greetings -------------------
        cat_greetings = Category.objects.create(
            course=course,
            slug='greetings',
            title_ky='Саламдашуу',
            title_target='Greetings',
            description_ky='Адамдар менен саламдашууну жана коштошууну үйрөнүңүз.',
            icon='hand',
            sort_order=1
        )

        # Lesson 1.1
        l1 = Lesson.objects.create(category=cat_greetings, slug='basic-hello', title='Hello & Goodbye',
                                   description_ky='Эң негизги саламдашуу сөздөрү.', xp_reward=50, sort_order=1)
        self._add_basic_hello(l1, create_tg, create_cu)

        # Lesson 1.2
        l2 = Lesson.objects.create(category=cat_greetings, slug='introducing-yourself', title='Introducing Yourself',
                                   description_ky='Өзүңүздү тааныштыруу.', xp_reward=70, sort_order=2)
        self._add_introducing_yourself(l2, create_tg, create_cu)

        # Lesson 1.3
        l3 = Lesson.objects.create(category=cat_greetings, slug='formal-informal', title='Formal vs Informal',
                                   description_ky='Расмий жана бейрасмий саламдашуу.', xp_reward=65, sort_order=3)
        self._add_formal_informal(l3, create_tg, create_cu)

        # Lesson 1.4
        l4 = Lesson.objects.create(category=cat_greetings, slug='thanks-politeness', title='Thank You & Politeness',
                                   description_ky='Рахмат айтуу жана сылык сөздөр.', xp_reward=60, sort_order=4)
        self._add_thanks_politeness(l4, create_tg, create_cu)

        # ------------------- Category: Food & Drinks -------------------
        cat_food = Category.objects.create(
            course=course,
            slug='food-drinks',
            title_ky='Тамак-аш жана суусундуктар',
            title_target='Food & Drinks',
            description_ky='Күнүмдүк тамак-аш жана суусундуктар жөнүндө сүйлөшүү.',
            icon='utensils',
            sort_order=2
        )

        food_lessons = [
            ("Water and Basic Food", "Суу жана негизги азыктар", 1),
            ("Fruits and Vegetables", "Жемиштер жана жашылчалар", 2),
            ("Ordering in a Cafe", "Кафеде тамак заказ кылуу", 3),
            ("At the Market", "Базарда сүйлөшүү", 4),
            ("Breakfast and Daily Meals", "Эртең мененки тамак жана тамак түрлөрү", 5),
        ]

        for i, (title_en, desc_ky, order) in enumerate(food_lessons, 1):
            lesson = Lesson.objects.create(
                category=cat_food,
                slug=slugify(title_en),
                title=title_en,
                description_ky=desc_ky,
                xp_reward=55 + i * 10,
                sort_order=order
            )
            self._add_food_lesson(lesson, i, create_tg, create_cu)

    # ====================== RUSSIAN COURSE ======================
    def _seed_russian_course(self, course, create_tg, create_cu):
        cat_greetings = Category.objects.create(
            course=course,
            slug='greetings',
            title_ky='Саламдашуу',
            title_target='Приветствия',
            description_ky='Орус тилинде саламдашууну үйрөнүңүз.',
            icon='hand',
            sort_order=1
        )

        l1 = Lesson.objects.create(
            category=cat_greetings,
            slug='basic-hello-ru',
            title='Здравствуй и До свидания',
            description_ky='Негизги саламдашуу сөздөрү.',
            xp_reward=50,
            sort_order=1
        )
        self._add_basic_hello_russian(l1, create_tg, create_cu)

        # Food category for Russian
        cat_food = Category.objects.create(
            course=course,
            slug='food-drinks-ru',
            title_ky='Тамак-аш жана суусундуктар',
            title_target='Еда и напитки',
            description_ky='Орус тилинде тамак-аш темасы.',
            icon='utensils',
            sort_order=2
        )

        l2 = Lesson.objects.create(
            category=cat_food,
            slug='basic-food-ru',
            title='Вода, хлеб и основные продукты',
            description_ky='Суу, нан жана негизги азыктар.',
            xp_reward=60,
            sort_order=1
        )
        self._add_basic_food_russian(l2, create_tg, create_cu)

    # ====================== LESSON IMPLEMENTATIONS ======================

    def _add_basic_hello(self, lesson, create_tg, create_cu):
        # Vocabulary
        create_cu('word', 'Hello', 'Салам')
        create_cu('word', 'Hi', 'Салам (бейрасмий)')
        create_cu('word', 'Goodbye', 'Жакшы калыңыз')
        create_cu('word', 'See you', 'Көрүшкөнчө')

        LessonVocabulary.objects.create(lesson=lesson, word_or_phrase_target='Hello',
                                        translation_ky='Салам', content_unit=create_cu('word', 'Hello', 'Салам'), sort_order=1)

        # Steps
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='multiple_choice',
            prompt='How do you say "Салам" in English?',
            prompt_group=create_tg({'ky': '"Салам" англисче кандай болот?', 'en': 'How do you say "Hello" in English?'}),
            sort_order=1
        )
        step = lesson.steps.get(sort_order=1).detail
        StepChoice.objects.bulk_create([
            StepChoice(step_detail=step, text='Hello', is_correct=True, sort_order=1),
            StepChoice(step_detail=step, text='Apple', is_correct=False, sort_order=2),
            StepChoice(step_detail=step, text='Water', is_correct=False, sort_order=3),
        ])

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='fill_blank',
            prompt='Complete the greeting',
            sort_order=2,
            detail_data={'sentence_template': '[[blank]], my name is John.', 'acceptable_answers': ['Hello', 'Hi']}
        )

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='match_pairs',
            prompt='Match the words',
            sort_order=3,
            detail_data={}
        )
        step3 = lesson.steps.get(sort_order=3).detail
        MatchPairItem.objects.bulk_create([
            MatchPairItem(step_detail=step3, left_text='Hello', right_text='Салам', sort_order=1),
            MatchPairItem(step_detail=step3, left_text='Goodbye', right_text='Жакшы калыңыз', sort_order=2),
        ])

    def _add_introducing_yourself(self, lesson, create_tg, create_cu):
        create_cu('phrase', "My name is ...", "Менин атым ...")
        create_cu('phrase', "I am from Kyrgyzstan", "Мен Кыргызстанданмын")

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Translate into English',
            sort_order=1,
            detail_data={'source_text': 'Менин атым Адил.', 'acceptable_answers': ['My name is Adil.', 'I am Adil.']}
        )

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='speak_phrase',
            prompt='Introduce yourself',
            sort_order=2,
            detail_data={'target_text': 'Hello, my name is John. I am from Bishkek.', 'min_score_required': 65}
        )

    def _add_formal_informal(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='multiple_choice',
            prompt='Which greeting is more formal?',
            sort_order=1,
            prompt_group=create_tg({'ky': 'Кайсы саламдашуу расмийрээк?', 'en': 'Which greeting is more formal?'})
        )
        # Добавь choices по желанию...

    def _add_thanks_politeness(self, lesson, create_tg, create_cu):
        create_cu('word', 'Thank you', 'Рахмат')
        create_cu('word', 'Please', 'Өтүнөм')
        create_cu('word', "You're welcome", 'Эч нерсе эмес')

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='reorder_sentence',
            prompt='Put the words in order: Thank you very much',
            sort_order=1,
            detail_data={}
        )
        step = lesson.steps.get(sort_order=1).detail
        ReorderToken.objects.bulk_create([
            ReorderToken(step_detail=step, text='Thank', sort_order=1),
            ReorderToken(step_detail=step, text='you', sort_order=2),
            ReorderToken(step_detail=step, text='very', sort_order=3),
            ReorderToken(step_detail=step, text='much', sort_order=4),
        ])

    def _add_food_lesson(self, lesson, lesson_num, create_tg, create_cu):
        # Разные типы шагов для каждого урока
        if lesson_num == 1:
            create_cu('word', 'Water', 'Суу')
            create_cu('word', 'Bread', 'Нан')
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type='type_translation',
                                                       prompt='Translate "Нан"', sort_order=1,
                                                       detail_data={'source_text': 'Нан', 'acceptable_answers': ['Bread']})
        elif lesson_num == 3:
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type='speak_phrase',
                                                       prompt='Order water in a cafe', sort_order=1,
                                                       detail_data={'target_text': 'Can I have a glass of water, please?'})
        else:
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type='multiple_choice',
                                                       prompt='What is "Алма" in English?', sort_order=1,
                                                       prompt_group=create_tg({'ky': '"Алма" англисче эмне?', 'en': 'What is "Apple" in English?'}))
            # Можно добавить больше шагов...

    # Russian lessons (базовые примеры)
    def _add_basic_hello_russian(self, lesson, create_tg, create_cu):
        create_cu('word', 'Здравствуй', 'Салам')
        create_cu('word', 'До свидания', 'Жакшы калыңыз')

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='match_pairs',
            prompt='Match Russian and Kyrgyz',
            sort_order=1
        )

    def _add_basic_food_russian(self, lesson, create_tg, create_cu):
        create_cu('word', 'Вода', 'Суу')
        create_cu('word', 'Хлеб', 'Нан')

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Translate into Russian',
            sort_order=1,
            detail_data={'source_text': 'Суу', 'acceptable_answers': ['Вода']}
        )

    def _create_demo_user(self, course_en, course_ru=None):
        from django.contrib.auth import get_user_model
        from lessons.services.course_enrollment_service import CourseEnrollmentService
        from lessons.services.category_progress_service import CategoryProgressService

        User = get_user_model()
        user, created = User.objects.get_or_create(
            nickname='demo_student',
            defaults={'email': 'demo@example.com', 'is_active': True}
        )

        if created:
            user.set_password('demo1234')
            user.save()
            self.stdout.write("Demo user created.")

        for course in [course_en, course_ru]:
            if course:
                CourseEnrollmentService.ensure_enrollment(user, course)

        for category in Category.objects.filter(course__in=[c for c in [course_en, course_ru] if c]):
            CategoryProgressService.update_category_progress(user, category)

        self.stdout.write(self.style.SUCCESS("Demo user 'demo_student' (password: demo1234) enrolled successfully!"))