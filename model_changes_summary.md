# Proposed Model Changes Summary

## 1. New App: `lessons`
A new set of models has been created in `lessons/models.py` based on the provided `db_schema.txt`. These models include:
- `Course`: Top-level container for learning content.
- `Unit`: Chapters within a course.
- `Category`: Grouping for lessons (can span multiple units or be standalone).
- `Lesson`: Individual learning units.
- `LessonStep`: Interactive steps within a lesson (vocab intro, multiple choice, etc.).
- `LessonVocabulary`: Specific words/phrases taught in a lesson.
- `CourseEnrollment`: Tracking user enrollment in courses.
- `UserLessonProgress`: Tracking individual user progress on lessons.
- `UserCategoryProgress`: Tracking progress at the category level.
- `ReviewItem`: Spaced repetition system items.
- `UserSkillProgress`: Tracking reading, writing, listening, and speaking skills.

## 2. Existing Model Changes: `apps/users/models.py` (User Model)

To fully integrate with the new `lessons` system, I recommend adding the following fields to the `User` model:

```python
# apps/users/models.py

class User(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...

    # Language Preferences
    native_language = models.CharField(max_length=10, default='ky', help_text="User's native language")
    target_language = models.CharField(max_length=10, default='tr', help_text="Language the user is learning")

    # Learning Progress & Stats
    # Note: 'points' already exists and can be used as 'xp'
    longest_streak = models.IntegerField(default=0, help_text="Highest streak achieved")
    onboarding_completed = models.BooleanField(default=False)
    current_course = models.ForeignKey(
        'lessons.Course', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='current_users'
    )
    daily_goal_xp = models.IntegerField(default=20, help_text="Daily XP goal set by user")
    total_lessons_completed = models.IntegerField(default=0)
    current_timezone = models.CharField(max_length=100, null=True, blank=True)

    # Note: is_premium can be derived from the 'subscription' app, 
    # but could be added here for convenience/performance if needed.
```

## 3. Configuration Changes: `BilimAI/settings.py`

Don't forget to add the `lessons` app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'lessons',
]
```

## 4. Architectural Notes
- **UUIDs**: All new models use `UUIDField` for primary keys to ensure consistency with the provided schema and better scalability.
- **Languages**: Standardized on ISO language codes (e.g., 'ky', 'tr').
- **JSONFields**: Used for `LessonStep` content and options to allow for flexible exercise types without changing the database schema.
