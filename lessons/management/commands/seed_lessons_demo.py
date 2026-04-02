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
        if lesson_num == 1:
            self._add_basic_hello(lesson, create_tg, create_cu)
        elif lesson_num == 2:
            self._add_introducing_yourself(lesson, create_tg, create_cu)
        else:
            # Fallback for other lessons to ensure they also have quality content
            self._add_generic_high_quality_lesson(lesson, create_tg, create_cu)

    def _add_basic_hello(self, lesson, create_tg, create_cu):
        # 1. Vocabulary (8-15 units)
        vocab = [
            ('word', 'Hello', 'Салам / Саламатсызбы'),
            ('word', 'Hi', 'Салам'),
            ('word', 'Goodbye', 'Жакшы калыңыз'),
            ('word', 'Bye', 'Жакшы кал'),
            ('phrase', 'Good morning', 'Кутмандуу таңыңыз менен'),
            ('phrase', 'Good afternoon', 'Кутмандуу күнүңүз менен'),
            ('phrase', 'Good evening', 'Кутмандуу кечиңиз менен'),
            ('phrase', 'How are you?', 'Кандайсыз?'),
            ('phrase', 'I am fine', 'Мен жакшымын'),
            ('phrase', 'Thank you', 'Рахмат'),
            ('phrase', 'Nice to meet you', 'Сиз менен таанышканыма кубанычтамын'),
            ('phrase', 'See you', 'Көрүшкөнчө'),
        ]
        
        cu_map = {}
        for i, (vtype, target, translation) in enumerate(vocab):
            cu = create_cu(vtype, target, translation)
            cu_map[target] = cu
            LessonVocabulary.objects.get_or_create(
                lesson=lesson, word_or_phrase_target=target,
                defaults={'translation_ky': translation, 'sort_order': i}
            )

        # 2. Steps (16 steps: Intro -> Vocab -> Practice -> Interaction -> Reinforcement)
        steps = [
            # Introduction & Basic Recognition
            ('multiple_choice', 'How do you say "Салам" in English?', {'choices': [{'content_unit': cu_map['Hello'], 'is_correct': True}, {'text': 'Goodbye', 'is_correct': False}, {'text': 'Fine', 'is_correct': False}]}),
            ('multiple_choice', 'What does "Goodbye" mean?', {'choices': [{'text': 'Жакшы калыңыз', 'is_correct': True}, {'text': 'Салам', 'is_correct': False}, {'text': 'Рахмат', 'is_correct': False}]}),
            ('match_pairs', 'Match the words', {'pairs': [{'left_text': 'Hello', 'right_text': 'Салам'}, {'left_text': 'Hi', 'right_text': 'Салам (бейрасмий)'}, {'left_text': 'Goodbye', 'right_text': 'Жакшы калыңыз'}, {'left_text': 'Bye', 'right_text': 'Жакшы кал'}]}),
            
            # Translation Practice
            ('type_translation', 'Translate "Салам"', {'source_text': 'Салам', 'acceptable_answers': ['Hello', 'Hi']}),
            ('type_translation', 'Translate "Жакшы калыңыз"', {'source_text': 'Жакшы калыңыз', 'acceptable_answers': ['Goodbye']}),
            
            # Sentence Building
            ('reorder_sentence', 'Build: "Hello, how are you?"', {'tokens': [{'text': 'Hello,', 'is_distractor': False}, {'text': 'how', 'is_distractor': False}, {'text': 'are', 'is_distractor': False}, {'text': 'you?', 'is_distractor': False}, {'text': 'Fine', 'is_distractor': True}]}),
            
            # New Vocabulary & Recognition
            ('multiple_choice', 'Choose "Кутмандуу таңыңыз менен"', {'choices': [{'content_unit': cu_map['Good morning'], 'is_correct': True}, {'text': 'Good night', 'is_correct': False}, {'text': 'Hello', 'is_correct': False}]}),
            ('match_pairs', 'Match greetings', {'pairs': [{'left_text': 'Good morning', 'right_text': 'Кутмандуу таң'}, {'left_text': 'Good evening', 'right_text': 'Кутмандуу кеч'}, {'left_text': 'Thank you', 'right_text': 'Рахмат'}]}),
            
            # Sentence Building & Interaction
            ('reorder_sentence', 'Build: "I am fine, thank you."', {'tokens': [{'text': 'I', 'is_distractor': False}, {'text': 'am', 'is_distractor': False}, {'text': 'fine,', 'is_distractor': False}, {'text': 'thank', 'is_distractor': False}, {'text': 'you.', 'is_distractor': False}]}),
            ('speak_phrase', 'Say "Good afternoon"', {'target_text': 'Good afternoon'}),
            
            # Context / Dialogue
            ('multiple_choice', 'You meet someone for the first time. You say:', {'choices': [{'text': 'Nice to meet you', 'is_correct': True}, {'text': 'Goodbye', 'is_correct': False}, {'text': 'I am fine', 'is_correct': False}]}),
            ('type_translation', 'Translate "Сиз менен таанышканыма кубанычтамын"', {'source_text': 'Сиз менен таанышканыма кубанычтамын', 'acceptable_answers': ['Nice to meet you']}),
            
            # Reinforcement
            ('reorder_sentence', 'Build: "See you later"', {'tokens': [{'text': 'See', 'is_distractor': False}, {'text': 'you', 'is_distractor': False}, {'text': 'later', 'is_distractor': False}, {'text': 'Hello', 'is_distractor': True}]}),
            ('speak_phrase', 'Say "Hello! Nice to meet you."', {'target_text': 'Hello! Nice to meet you.'}),
            ('match_pairs', 'Final Review', {'pairs': [{'left_text': 'See you', 'right_text': 'Көрүшкөнчө'}, {'left_text': 'I am fine', 'right_text': 'Жакшымын'}, {'left_text': 'Thank you', 'right_text': 'Рахмат'}, {'left_text': 'Hi', 'right_text': 'Салам'}]}),
            ('type_translation', 'Translate "Көрүшкөнчө"', {'source_text': 'Көрүшкөнчө', 'acceptable_answers': ['See you', 'Bye']}),
        ]

        for i, (stype, prompt, data) in enumerate(steps, 1):
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)

    def _add_introducing_yourself(self, lesson, create_tg, create_cu):
        # Vocabulary
        vocab = [
            ('phrase', 'What is your name?', 'Атыңыз ким?'),
            ('phrase', 'My name is ...', 'Менин атым ...'),
            ('word', 'Student', 'Студент'),
            ('word', 'Teacher', 'Мугалим'),
            ('word', 'Kyrgyzstan', 'Кыргызстан'),
            ('phrase', 'I am from ...', 'Мен ...дан болом'),
            ('phrase', 'Where are you from?', 'Сиз кайдан болосуз?'),
        ]
        cu_map = {}
        for i, (vtype, target, translation) in enumerate(vocab):
            cu = create_cu(vtype, target, translation)
            cu_map[target] = cu
            LessonVocabulary.objects.get_or_create(lesson=lesson, word_or_phrase_target=target, defaults={'translation_ky': translation, 'sort_order': i})

        steps = [
            ('multiple_choice', 'How to ask "Атыңыз ким?"', {'choices': [{'text': 'What is your name?', 'is_correct': True}, {'text': 'How are you?', 'is_correct': False}, {'text': 'Who are you?', 'is_correct': False}]}),
            ('type_translation', 'Translate "Менин атым Адил"', {'source_text': 'Менин атым Адил', 'acceptable_answers': ['My name is Adil']}),
            ('match_pairs', 'Match roles and places', {'pairs': [{'left_text': 'Student', 'right_text': 'Студент'}, {'left_text': 'Teacher', 'right_text': 'Мугалим'}, {'left_text': 'Kyrgyzstan', 'right_text': 'Кыргызстан'}]}),
            ('reorder_sentence', 'Build: "I am a student"', {'tokens': [{'text': 'I', 'is_distractor': False}, {'text': 'am', 'is_distractor': False}, {'text': 'a', 'is_distractor': False}, {'text': 'student', 'is_distractor': False}, {'text': 'teacher', 'is_distractor': True}]}),
            ('multiple_choice', 'Ask "Сиз кайдан болосуз?"', {'choices': [{'text': 'Where are you from?', 'is_correct': True}, {'text': 'Where do you live?', 'is_correct': False}]}),
            ('type_translation', 'Translate "Мен Кыргызстанданмын"', {'source_text': 'Мен Кыргызстанданмын', 'acceptable_answers': ['I am from Kyrgyzstan']}),
            ('speak_phrase', 'Say "My name is John"', {'target_text': 'My name is John'}),
            ('reorder_sentence', 'Build: "Where are you from?"', {'tokens': [{'text': 'Where', 'is_distractor': False}, {'text': 'are', 'is_distractor': False}, {'text': 'you', 'is_distractor': False}, {'text': 'from?', 'is_distractor': False}]}),
            ('multiple_choice', 'Respond to "Where are you from?"', {'choices': [{'text': 'I am from Kyrgyzstan', 'is_correct': True}, {'text': 'My name is Kyrgyzstan', 'is_correct': False}]}),
            ('speak_phrase', 'Say "I am a teacher"', {'target_text': 'I am a teacher'}),
            ('match_pairs', 'Final Review', {'pairs': [{'left_text': 'What is your name?', 'right_text': 'Атыңыз ким?'}, {'left_text': 'Where are you from?', 'right_text': 'Кайдан болосуз?'}, {'left_text': 'Student', 'right_text': 'Студент'}]}),
            ('type_translation', 'Translate "Атыңыз ким?"', {'source_text': 'Атыңыз ким?', 'acceptable_answers': ['What is your name?']}),
        ]
        for i, (stype, prompt, data) in enumerate(steps, 1):
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)

    def _add_generic_high_quality_lesson(self, lesson, create_tg, create_cu):
        # Simple fallback with 12 steps
        for i in range(1, 13):
            stype = 'multiple_choice' if i % 3 == 0 else 'type_translation' if i % 3 == 1 else 'match_pairs'
            prompt = f'Practice Step {i} for {lesson.title}'
            data = {}
            if stype == 'multiple_choice':
                data = {'choices': [{'text': 'Correct', 'is_correct': True}, {'text': 'Wrong', 'is_correct': False}]}
            elif stype == 'type_translation':
                data = {'source_text': 'Текст', 'acceptable_answers': ['Text']}
            elif stype == 'match_pairs':
                data = {'pairs': [{'left_text': 'A', 'right_text': '1'}, {'left_text': 'B', 'right_text': '2'}]}
            
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)

    def _add_food_lesson(self, lesson, lesson_num, create_tg, create_cu):
        # 1. Vocabulary
        vocab = [
            ('word', 'Bread', 'Нан'),
            ('word', 'Water', 'Суу'),
            ('word', 'Coffee', 'Кофе'),
            ('word', 'Tea', 'Чай'),
            ('word', 'Milk', 'Сүт'),
            ('word', 'Apple', 'Алма'),
            ('phrase', 'I want ...', 'Мен ... каалайм'),
            ('phrase', 'I would like ...', 'Мен ... алсам болобу / Мен ... каалайт элем'),
            ('phrase', 'Please', 'Сураныч'),
            ('phrase', 'How much is it?', 'Бул канча турат?'),
        ]
        cu_map = {}
        for i, (vtype, target, translation) in enumerate(vocab):
            cu = create_cu(vtype, target, translation)
            cu_map[target] = cu
            LessonVocabulary.objects.get_or_create(lesson=lesson, word_or_phrase_target=target, defaults={'translation_ky': translation, 'sort_order': i})

        steps = [
            ('multiple_choice', 'Choose "Нан"', {'choices': [{'content_unit': cu_map['Bread'], 'is_correct': True}, {'text': 'Water', 'is_correct': False}, {'text': 'Apple', 'is_correct': False}]}),
            ('multiple_choice', 'What is "Water"?', {'choices': [{'text': 'Суу', 'is_correct': True}, {'text': 'Нан', 'is_correct': False}, {'text': 'Чай', 'is_correct': False}]}),
            ('match_pairs', 'Match drinks', {'pairs': [{'left_text': 'Coffee', 'right_text': 'Кофе'}, {'left_text': 'Tea', 'right_text': 'Чай'}, {'left_text': 'Milk', 'right_text': 'Сүт'}, {'left_text': 'Water', 'right_text': 'Суу'}]}),
            ('type_translation', 'Translate "Нан"', {'source_text': 'Нан', 'acceptable_answers': ['Bread']}),
            ('type_translation', 'Translate "Сүт"', {'source_text': 'Сүт', 'acceptable_answers': ['Milk']}),
            ('reorder_sentence', 'Build: "I want water"', {'tokens': [{'text': 'I', 'is_distractor': False}, {'text': 'want', 'is_distractor': False}, {'text': 'water', 'is_distractor': False}, {'text': 'bread', 'is_distractor': True}]}),
            ('speak_phrase', 'Say "A cup of tea, please"', {'target_text': 'A cup of tea, please'}),
            ('multiple_choice', 'How to say "Сураныч"?', {'choices': [{'text': 'Please', 'is_correct': True}, {'text': 'Thanks', 'is_correct': False}]}),
            ('reorder_sentence', 'Build: "I would like an apple"', {'tokens': [{'text': 'I', 'is_distractor': False}, {'text': 'would', 'is_distractor': False}, {'text': 'like', 'is_distractor': False}, {'text': 'an', 'is_distractor': False}, {'text': 'apple', 'is_distractor': False}]}),
            ('multiple_choice', 'Ask "Бул канча турат?"', {'choices': [{'text': 'How much is it?', 'is_correct': True}, {'text': 'What is it?', 'is_correct': False}]}),
            ('speak_phrase', 'Say "Bread and water"', {'target_text': 'Bread and water'}),
            ('match_pairs', 'Final Review', {'pairs': [{'left_text': 'Bread', 'right_text': 'Нан'}, {'left_text': 'Apple', 'right_text': 'Алма'}, {'left_text': 'Water', 'right_text': 'Суу'}]}),
            ('type_translation', 'Translate "Сураныч, мага кофе"', {'source_text': 'Сураныч, мага кофе', 'acceptable_answers': ['Coffee please', 'Coffee, please']}),
        ]
        for i, (stype, prompt, data) in enumerate(steps, 1):
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)

    # ====================== УРОКИ ДЛЯ RUSSIAN ======================
    def _add_basic_hello_russian(self, lesson, create_tg, create_cu):
        # Vocabulary
        vocab = [
            ('word', 'Привет', 'Салам'),
            ('word', 'Здравствуйте', 'Саламатсызбы'),
            ('word', 'Пока', 'Жакшы кал'),
            ('word', 'До свидания', 'Жакшы калыңыз'),
            ('phrase', 'Как дела?', 'Кандайсың?'),
            ('phrase', 'Хорошо', 'Жакшы'),
            ('phrase', 'Спасибо', 'Рахмат'),
        ]
        cu_map = {}
        for i, (vtype, target, translation) in enumerate(vocab):
            cu = create_cu(vtype, target, translation)
            cu_map[target] = cu
            LessonVocabulary.objects.get_or_create(lesson=lesson, word_or_phrase_target=target, defaults={'translation_ky': translation, 'sort_order': i})

        steps = [
            ('multiple_choice', 'Как сказать "Салам" (неформально)?', {'choices': [{'content_unit': cu_map['Привет'], 'is_correct': True}, {'text': 'Пока', 'is_correct': False}]}),
            ('multiple_choice', 'Как сказать "Саламатсызбы"?', {'choices': [{'text': 'Здравствуйте', 'is_correct': True}, {'text': 'Привет', 'is_correct': False}]}),
            ('match_pairs', 'Сопоставьте слова', {'pairs': [{'left_text': 'Привет', 'right_text': 'Салам'}, {'left_text': 'Пока', 'right_text': 'Жакшы кал'}, {'left_text': 'Спасибо', 'right_text': 'Рахмат'}]}),
            ('type_translation', 'Переведите "Салам"', {'source_text': 'Салам', 'acceptable_answers': ['Привет']}),
            ('reorder_sentence', 'Соберите: "Привет, как дела?"', {'tokens': [{'text': 'Привет,', 'is_distractor': False}, {'text': 'как', 'is_distractor': False}, {'text': 'дела?', 'is_distractor': False}]}),
            ('multiple_choice', 'Ответ на "Как дела?": "Жакшы, рахмат"', {'choices': [{'text': 'Хорошо, спасибо', 'is_correct': True}, {'text': 'Пока, спасибо', 'is_correct': False}]}),
            ('speak_phrase', 'Скажите "До свидания"', {'target_text': 'До свидания'}),
            ('type_translation', 'Переведите "Жакшы"', {'source_text': 'Жакшы', 'acceptable_answers': ['Хорошо']}),
            ('match_pairs', 'Проверка', {'pairs': [{'left_text': 'Здравствуйте', 'right_text': 'Саламатсызбы'}, {'left_text': 'До свидания', 'right_text': 'Жакшы калыңыз'}]}),
            ('reorder_sentence', 'Соберите: "Спасибо, хорошо"', {'tokens': [{'text': 'Спасибо,', 'is_distractor': False}, {'text': 'хорошо', 'is_distractor': False}]}),
            ('speak_phrase', 'Скажите "Привет!"', {'target_text': 'Привет!'}),
            ('type_translation', 'Переведите "Жакшы калыңыз"', {'source_text': 'Жакшы калыңыз', 'acceptable_answers': ['До свидания']}),
        ]
        for i, (stype, prompt, data) in enumerate(steps, 1):
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)

    def _add_basic_food_russian(self, lesson, create_tg, create_cu):
        steps = [
            ('multiple_choice', 'Выберите "Вода"', {'choices': [{'text': 'Вода', 'is_correct': True}, {'text': 'Хлеб', 'is_correct': False}]}),
            ('type_translation', 'Переведите "Нан"', {'source_text': 'Нан', 'acceptable_answers': ['Хлеб']}),
            ('match_pairs', 'Сопоставьте', {'pairs': [{'left_text': 'Вода', 'right_text': 'Суу'}, {'left_text': 'Хлеб', 'right_text': 'Нан'}]}),
            ('reorder_sentence', 'Соберите: "Я хочу хлеб"', {'tokens': [{'text': 'Я', 'is_distractor': False}, {'text': 'хочу', 'is_distractor': False}, {'text': 'хлеб', 'is_distractor': False}]}),
            ('speak_phrase', 'Скажите "Дайте воду, пожалуйста"', {'target_text': 'Дайте воду, пожалуйста'}),
            ('multiple_choice', 'Что такое "Чай"?', {'choices': [{'text': 'Чай', 'is_correct': True}, {'text': 'Кофе', 'is_correct': False}]}),
            ('type_translation', 'Переведите "Кофе"', {'source_text': 'Кофе', 'acceptable_answers': ['Кофе']}),
            ('match_pairs', 'Напитки', {'pairs': [{'left_text': 'Чай', 'right_text': 'Чай'}, {'left_text': 'Кофе', 'right_text': 'Кофе'}]}),
            ('reorder_sentence', 'Соберите: "Можно мне чай?"', {'tokens': [{'text': 'Можно', 'is_distractor': False}, {'text': 'мне', 'is_distractor': False}, {'text': 'чай?', 'is_distractor': False}]}),
            ('speak_phrase', 'Скажите "Хлеб и чай"', {'target_text': 'Хлеб и чай'}),
            ('multiple_choice', 'Как сказать "Рахмат"?', {'choices': [{'text': 'Спасибо', 'is_correct': True}, {'text': 'Пожалуйста', 'is_correct': False}]}),
            ('type_translation', 'Переведите "Суу сураныч"', {'source_text': 'Суу сураныч', 'acceptable_answers': ['Воду пожалуйста', 'Воду, пожалуйста']}),
        ]
        for i, (stype, prompt, data) in enumerate(steps, 1):
            ContentAuthoringService.create_lesson_step(lesson=lesson, step_type=stype, prompt=prompt, sort_order=i, detail_data=data)


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