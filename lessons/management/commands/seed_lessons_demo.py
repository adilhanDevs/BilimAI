from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from lessons.models.localization import Language, TranslationGroup, Translation
from lessons.models.course import Course, Category, Lesson, LessonVocabulary
from lessons.models.engine import ContentUnit, StepChoice, MatchPairItem, ReorderToken
from lessons.services.authoring_service import ContentAuthoringService


class Command(BaseCommand):
    help = "Seeds clean demo courses with 4 high-quality lessons per category"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing demo data before seeding')
        parser.add_argument('--with-user', action='store_true', help='Create demo user and enroll')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING("Resetting demo data..."))
            Course.objects.filter(slug__in=['english-for-kyrgyz', 'russian-for-kyrgyz']).delete()

        # Languages
        en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        ky, _ = Language.objects.get_or_create(code='ky', defaults={'name': 'Kyrgyz'})
        ru, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Russian'})

        def create_tg(texts_dict: dict):
            tg = TranslationGroup.objects.create()
            for lang_code, text in texts_dict.items():
                lang = Language.objects.get(code=lang_code)
                Translation.objects.create(group=tg, language=lang, text=text)
            return tg

        def create_cu(unit_type: str, text_en: str, meaning_ky: str, ky_text=None):
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
        course_en, _ = Course.objects.get_or_create(
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

        self._seed_english_course(course_en, create_tg, create_cu)

        # ==================== RUSSIAN FOR KYRGYZ ====================
        course_ru, _ = Course.objects.get_or_create(
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

        self._seed_russian_course(course_ru, create_tg, create_cu)

        if options.get('with_user'):
            self._create_demo_user(course_en, course_ru)

        self.stdout.write(self.style.SUCCESS("✅ Seeding completed successfully!"))

    # ====================== ENGLISH COURSE ======================
    def _seed_english_course(self, course, create_tg, create_cu):
        # Category 1: Greetings (4 урока)
        cat_greetings, _ = Category.objects.get_or_create(
            course=course,
            slug='greetings',
            defaults={
                'title_ky': 'Саламдашуу',
                'title_target': 'Greetings',
                'description_ky': 'Адамдар менен саламдашууну жана коштошууну үйрөнүңүз.',
                'icon': 'hand',
                'sort_order': 1
            }
        )

        greetings = [
            ("basic-hello", "Hello & Goodbye", "Эң негизги саламдашуу сөздөрү.", 1),
            ("introducing-yourself", "Introducing Yourself", "Өзүңүздү тааныштыруу.", 2),
            ("formal-informal", "Formal vs Informal", "Расмий жана бейрасмий саламдашуу.", 3),
            ("thanks-politeness", "Thank You & Politeness", "Рахмат айтуу жана сылык сөздөр.", 4),
        ]

        for slug, title, desc_ky, order in greetings:
            lesson = Lesson.objects.create(
                category=cat_greetings,
                slug=slug,
                title=title,
                description_ky=desc_ky,
                xp_reward=50 + order * 10,
                sort_order=order
            )
            if order == 1:
                self._add_basic_hello(lesson, create_tg, create_cu)
            elif order == 2:
                self._add_introducing_yourself(lesson, create_tg, create_cu)
            elif order == 3:
                self._add_formal_informal(lesson, create_tg, create_cu)
            elif order == 4:
                self._add_thanks_politeness(lesson, create_tg, create_cu)

        # Category 2: Food & Drinks (4 урока)
        cat_food, _ = Category.objects.get_or_create(
            course=course,
            slug='food-drinks',
            defaults={
                'title_ky': 'Тамак-аш жана суусундуктар',
                'title_target': 'Food & Drinks',
                'description_ky': 'Күнүмдүк тамак-аш жана суусундуктар жөнүндө.',
                'icon': 'utensils',
                'sort_order': 2
            }
        )

        food_lessons = [
            ("water-basic-food", "Water and Basic Food", "Суу жана негизги азыктар.", 1),
            ("fruits-vegetables", "Fruits and Vegetables", "Жемиштер жана жашылчалар.", 2),
            ("ordering-cafe", "Ordering in a Cafe", "Кафеде тамак заказ кылуу.", 3),
            ("at-market", "At the Market", "Базарда сүйлөшүү.", 4),
        ]

        for slug, title, desc_ky, order in food_lessons:
            lesson = Lesson.objects.create(
                category=cat_food,
                slug=slug,
                title=title,
                description_ky=desc_ky,
                xp_reward=60 + order * 8,
                sort_order=order
            )
            self._add_food_lesson(lesson, order, create_tg, create_cu)

    # ====================== RUSSIAN COURSE ======================
    def _seed_russian_course(self, course, create_tg, create_cu):
        cat_greetings, _ = Category.objects.get_or_create(
            course=course,
            slug='greetings-ru',
            defaults={
                'title_ky': 'Саламдашуу',
                'title_target': 'Приветствия',
                'description_ky': 'Орус тилинде саламдашууну үйрөнүңүз.',
                'icon': 'hand',
                'sort_order': 1
            }
        )

        greetings_ru = [
            ("basic-hello-ru", "Здравствуй и До свидания", "Негизги саламдашуу сөздөрү.", 1),
            ("introducing-ru", "Представление себя", "Өзүңүздү тааныштыруу.", 2),
            ("formal-ru", "Формальное общение", "Расмий жана бейрасмий.", 3),
            ("thanks-ru", "Спасибо и вежливость", "Рахмат жана сылык сөздөр.", 4),
        ]

        for slug, title, desc_ky, order in greetings_ru:
            lesson = Lesson.objects.create(
                category=cat_greetings,
                slug=slug,
                title=title,
                description_ky=desc_ky,
                xp_reward=50 + order * 10,
                sort_order=order
            )
            self._add_basic_hello_russian(lesson, create_tg, create_cu)

        # Food category (4 урока)
        cat_food, _ = Category.objects.get_or_create(
            course=course,
            slug='food-drinks-ru',
            defaults={
                'title_ky': 'Тамак-аш жана суусундуктар',
                'title_target': 'Еда и напитки',
                'description_ky': 'Орус тилинде тамак-аш темасы.',
                'icon': 'utensils',
                'sort_order': 2
            }
        )

        food_ru = [
            ("basic-food-ru", "Вода и хлеб", "Суу жана нан.", 1),
            ("fruits-ru", "Фрукты и овощи", "Жемиштер жана жашылчалар.", 2),
            ("ordering-ru", "Заказ еды", "Кафеде заказ кылуу.", 3),
            ("market-ru", "На рынке", "Базарда.", 4),
        ]

        for slug, title, desc_ky, order in food_ru:
            lesson = Lesson.objects.create(
                category=cat_food,
                slug=slug,
                title=title,
                description_ky=desc_ky,
                xp_reward=60 + order * 8,
                sort_order=order
            )
            self._add_basic_food_russian(lesson, create_tg, create_cu)

    # ====================== QUALITY LESSON CONTENT ======================

    def _add_basic_hello(self, lesson, create_tg, create_cu):
        create_cu('word', 'Hello', 'Салам')
        create_cu('word', 'Hi', 'Салам')
        create_cu('word', 'Goodbye', 'Жакшы калыңыз')

        # Step 1: Multiple Choice
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

        # Step 2: Fill in the Blank
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='fill_blank',
            prompt='Complete the sentence',
            sort_order=2,
            detail_data={
                'sentence_template': '[[blank]], my name is John.',
                'acceptable_answers': ['Hello', 'Hi']
            }
        )

        # Step 3: Match Pairs
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='match_pairs',
            prompt='Match English words with Kyrgyz translations',
            sort_order=3
        )
        step3 = lesson.steps.get(sort_order=3).detail
        MatchPairItem.objects.bulk_create([
            MatchPairItem(step_detail=step3, left_text='Hello', right_text='Салам', sort_order=1),
            MatchPairItem(step_detail=step3, left_text='Goodbye', right_text='Жакшы калыңыз', sort_order=2),
        ])

    def _add_introducing_yourself(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Translate into English',
            sort_order=1,
            detail_data={
                'source_text': 'Менин атым Адил.',
                'acceptable_answers': ['My name is Adil.', 'I am Adil.']
            }
        )

    def _add_formal_informal(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='multiple_choice',
            prompt='Which greeting is more formal?',
            sort_order=1
        )

    def _add_thanks_politeness(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='reorder_sentence',
            prompt='Put the words in the correct order',
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

    def _add_food_lesson(self, lesson, order, create_tg, create_cu):
        if order == 1:
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='type_translation',
                prompt='Translate "Нан" into English',
                sort_order=1,
                detail_data={'source_text': 'Нан', 'acceptable_answers': ['Bread']}
            )
        else:
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='speak_phrase',
                prompt='Say the phrase clearly',
                sort_order=1,
                detail_data={
                    'target_text': 'Can I have a glass of water, please?',
                    'min_score_required': 70
                }
            )

    def _add_basic_hello_russian(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='match_pairs',
            prompt='Match Russian and Kyrgyz',
            sort_order=1
        )

    def _add_basic_food_russian(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Translate "Суу" into Russian',
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

        for course in [course_en, course_ru]:
            if course:
                CourseEnrollmentService.ensure_enrollment(user, course)

        for cat in Category.objects.filter(course__in=[c for c in [course_en, course_ru] if c]):
            CategoryProgressService.update_category_progress(user, cat)

        self.stdout.write(self.style.SUCCESS("Demo user 'demo_student' (password: demo1234) created and enrolled!"))