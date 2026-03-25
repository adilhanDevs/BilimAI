from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.gamification.models import ActivityLog
from apps.gamification.services.gamification_service import (
    DAILY_SESSION_POINTS,
    STREAK_BONUS_POINTS,
    GamificationService,
)
from apps.users.models import User


class GamificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            nickname="gm",
            email="gm@example.com",
            password="pass12345",
        )

    def test_daily_session_idempotent(self):
        first = GamificationService.record_daily_session(self.user)
        self.user.refresh_from_db()
        self.assertGreaterEqual(first["points"], DAILY_SESSION_POINTS)

        second = GamificationService.record_daily_session(self.user)
        self.assertEqual(first["points"], second["points"])
        logs = ActivityLog.objects.filter(user=self.user, activity_type=ActivityLog.ActivityType.DAILY_SESSION)
        self.assertEqual(logs.count(), 1)

    def test_streak_bonus_when_continuing_streak(self):
        user = User.objects.create_user(
            nickname="gm2",
            email="gm2@example.com",
            password="pass12345",
        )
        today = timezone.localdate()
        user.streak = 1
        user.last_streak_date = today - timedelta(days=1)
        user.save()

        GamificationService.record_daily_session(user)
        user.refresh_from_db()

        self.assertGreaterEqual(user.streak, 2)
        bonuses = ActivityLog.objects.filter(user=user, activity_type=ActivityLog.ActivityType.STREAK_BONUS)
        self.assertEqual(bonuses.count(), 1)
        self.assertEqual(bonuses.first().delta_points, STREAK_BONUS_POINTS)
