from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from lessons.models.localization import Language, TranslationGroup, Translation
from lessons.models.course import Course, Category, Lesson, LessonVocabulary
from lessons.models.engine import ContentUnit, StepChoice, MatchPairItem, ReorderToken
from lessons.services.authoring_service import ContentAuthoringService


class Command(BaseCommand):
    help = "Добавляет много реалистичных уроков в существующие категории курсов English-Kyrgyz и Russian-Kyrgyz"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Удалить существующие демо-данные перед заполнением')
        parser.add_argument('--with-user', action='store_true', help='Создать демо-пользователя и записать его на курсы')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING("Сброс демо-данных..."))
            Course.objects.filter(slug__in=['english-for-kyrgyz', 'russian-for-kyrgyz']).delete()

        # ==================== ЯЗЫКИ ====================
        self.stdout.write("Создание языков...")
        en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        ky, _ = Language.objects.get_or_create(code='ky', defaults={'name': 'Kyrgyz'})
        ru, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Russian'})

        # ==================== HELPER ФУНКЦИИ ====================
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

        self.stdout.write(f"Добавляем уроки в курс: {course_en.title}")
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

        self.stdout.write(f"Добавляем уроки в курс: {course_ru.title}")
        self._seed_russian_course(course_ru, create_tg, create_cu)

        # ==================== ДЕМО ПОЛЬЗОВАТЕЛЬ ====================
        if options.get('with_user'):
            self._create_demo_user(course_en, course_ru)

        self.stdout.write(self.style.SUCCESS("\n=== Заполнение базы данных успешно завершено! ==="))
        self.stdout.write(f"Уроков в English курсе: {Lesson.objects.filter(category__course=course_en).count()}")
        self.stdout.write(f"Уроков в Russian курсе: {Lesson.objects.filter(category__course=course_ru).count()}")

    # ====================== ENGLISH COURSE ======================
    def _seed_english_course(self, course, create_tg, create_cu):
        # --- Категория 1: Саламдашуу ---
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

        greetings_lessons = [
            ("basic-hello", "Hello & Goodbye", "Эң негизги саламдашуу сөздөрү.", 50),
            ("introducing-yourself", "Introducing Yourself", "Өзүңүздү тааныштыруу.", 70),
            ("formal-informal", "Formal vs Informal", "Расмий жана бейрасмий саламдашуу.", 65),
            ("thanks-politeness", "Thank You & Politeness", "Рахмат айтуу жана сылык сөздөр.", 60),
            ("small-talk", "Small Talk", "Жеңил баарлашуу.", 55),
            ("meeting-people", "Meeting New People", "Жаңы адамдар менен таанышуу.", 75),
            ("greetings-practice", "Greetings Practice", "Практика саламдашуу.", 45),
        ]

        for i, (slug, title, desc, xp) in enumerate(greetings_lessons, 1):
            lesson, created = Lesson.objects.get_or_create(
                category=cat_greetings,
                slug=slug,
                defaults={
                    'title': title,
                    'description_ky': desc,
                    'xp_reward': xp,
                    'sort_order': i
                }
            )
            if created:
                self._add_greetings_lesson(lesson, i, create_tg, create_cu)

        # --- Категория 2: Тамак-аш жана суусундуктар ---
        cat_food, _ = Category.objects.get_or_create(
            course=course,
            slug='food-drinks',
            defaults={
                'title_ky': 'Тамак-аш жана суусундуктар',
                'title_target': 'Food & Drinks',
                'description_ky': 'Күнүмдүк тамак-аш жана суусундуктар жөнүндө сүйлөшүү.',
                'icon': 'utensils',
                'sort_order': 2
            }
        )

        food_lessons = [
            ("water-basic", "Water and Basic Items", "Суу жана негизги азыктар.", 60),
            ("fruits-vegetables", "Fruits and Vegetables", "Жемиштер жана жашылчалар.", 65),
            ("ordering-cafe", "Ordering Food in Cafe", "Кафеде тамак заказ кылуу.", 80),
            ("at-market", "At the Market", "Базарда сүйлөшүү.", 70),
            ("breakfast-meals", "Breakfast and Daily Meals", "Эртең мененки тамак.", 55),
            ("restaurant-dialogue", "Restaurant Dialogue", "Ресторанда сүйлөшүү.", 85),
            ("favorite-food", "Talking About Favorite Food", "Сүйүктүү тамактар жөнүндө.", 75),
        ]

        for i, (slug, title, desc, xp) in enumerate(food_lessons, 1):
            lesson, created = Lesson.objects.get_or_create(
                category=cat_food,
                slug=slug,
                defaults={
                    'title': title,
                    'description_ky': desc,
                    'xp_reward': xp,
                    'sort_order': i
                }
            )
            if created:
                self._add_food_lesson(lesson, i, create_tg, create_cu)

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
            ("basic-hello-ru", "Здравствуй и До свидания", "Негизги саламдашуу.", 50),
            ("introducing-ru", "Представление себя", "Өзүңүздү тааныштыруу орусча.", 70),
            ("formal-ru", "Формальное и неформальное общение", "Расмий жана бейрасмий.", 65),
        ]

        for i, (slug, title, desc, xp) in enumerate(greetings_ru, 1):
            lesson, created = Lesson.objects.get_or_create(
                category=cat_greetings,
                slug=slug,
                defaults={'title': title, 'description_ky': desc, 'xp_reward': xp, 'sort_order': i}
            )
            if created:
                self._add_basic_hello_russian(lesson, create_tg, create_cu)

        # Food category for Russian
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
            ("basic-food-ru", "Вода и хлеб", "Суу жана нан.", 60),
            ("ordering-food-ru", "Заказ еды", "Тамак заказ кылуу.", 80),
        ]

        for i, (slug, title, desc, xp) in enumerate(food_ru, 1):
            lesson, created = Lesson.objects.get_or_create(
                category=cat_food,
                slug=slug,
                defaults={'title': title, 'description_ky': desc, 'xp_reward': xp, 'sort_order': i}
            )
            if created:
                self._add_basic_food_russian(lesson, create_tg, create_cu)

    # ====================== УРОКИ ДЛЯ ENGLISH ======================
    def _add_greetings_lesson(self, lesson, lesson_num, create_tg, create_cu):
        # Разные типы шагов в зависимости от урока
        if lesson_num == 1:
            self._add_basic_hello(lesson, create_tg, create_cu)
        elif lesson_num == 2:
            self._add_introducing_yourself(lesson, create_tg, create_cu)
        else:
            # Общий набор шагов для остальных уроков
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='multiple_choice',
                prompt='Choose the correct greeting', sort_order=1
            )
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='type_translation',
                prompt='Translate the phrase', sort_order=2
            )

    def _add_basic_hello(self, lesson, create_tg, create_cu):
        create_cu('word', 'Hello', 'Салам')
        create_cu('word', 'Goodbye', 'Жакшы калыңыз')

        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='multiple_choice',
            prompt='How do you say "Салам" in English?',
            prompt_group=create_tg({'ky': '"Салам" англисче кандай болот?', 'en': 'How do you say "Hello" in English?'}),
            sort_order=1
        )

    def _add_introducing_yourself(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Translate: Менин атым ...',
            sort_order=1,
            detail_data={'source_text': 'Менин атым Адил.', 'acceptable_answers': ['My name is Adil.']}
        )

    def _add_food_lesson(self, lesson, lesson_num, create_tg, create_cu):
        if lesson_num == 1:
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='type_translation',
                prompt='Translate "Нан"', sort_order=1,
                detail_data={'source_text': 'Нан', 'acceptable_answers': ['Bread']}
            )
        else:
            ContentAuthoringService.create_lesson_step(
                lesson=lesson, step_type='speak_phrase',
                prompt='Say the food order', sort_order=1
            )

    # ====================== УРОКИ ДЛЯ RUSSIAN ======================
    def _add_basic_hello_russian(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='match_pairs',
            prompt='Сопоставьте слова', sort_order=1
        )

    def _add_basic_food_russian(self, lesson, create_tg, create_cu):
        ContentAuthoringService.create_lesson_step(
            lesson=lesson, step_type='type_translation',
            prompt='Переведите на русский', sort_order=1,
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

        for category in Category.objects.filter(course__in=[c for c in [course_en, course_ru] if c]):
            CategoryProgressService.update_category_progress(user, category)

        self.stdout.write(self.style.SUCCESS(f"Демо-пользователь 'demo_student' (пароль: demo1234) создан и записан на курсы!"))