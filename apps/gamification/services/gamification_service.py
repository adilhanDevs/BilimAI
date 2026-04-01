from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.gamification.models import ActivityLog
from apps.users.models import User

logger = logging.getLogger(__name__)

DAILY_SESSION_POINTS = 10
STREAK_BONUS_POINTS = 50
MONTHLY_POINTS_FOR_REWARD = 1000


class GamificationService:
    @staticmethod
    def _local_today():
        return timezone.localdate()

    @staticmethod
    def _apply_level_rules(user: User) -> None:
        while user.points >= 1000:
            user.points -= 1000
            user.level += 1

    @staticmethod
    def _monthly_points_total(user: User) -> int:
        start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        agg = ActivityLog.objects.filter(user=user, created_at__gte=start).aggregate(total=Sum("delta_points"))
        return int(agg["total"] or 0)

    @staticmethod
    def _update_monthly_reward(user: User) -> None:
        total = GamificationService._monthly_points_total(user)
        if total >= MONTHLY_POINTS_FOR_REWARD and not user.monthly_reward_unlocked:
            user.monthly_reward_unlocked = True
            logger.info("Monthly reward unlocked for user_id=%s", user.pk)

    @staticmethod
    def _update_streak(user: User, today) -> None:
        if user.last_streak_date is None:
            user.streak = 1
        elif user.last_streak_date == today - timedelta(days=1):
            user.streak += 1
        elif user.last_streak_date == today:
            pass
        else:
            user.streak = 1
        
        if user.streak > user.longest_streak:
            user.longest_streak = user.streak
        
        user.last_streak_date = today

    @classmethod
    def record_daily_session(cls, user: User) -> dict:
        """Idempotent per local day: +10 session points; +50 streak bonus when streak >= 2."""
        today = cls._local_today()

        already = ActivityLog.objects.filter(
            user=user,
            activity_type=ActivityLog.ActivityType.DAILY_SESSION,
            created_at__date=today,
        ).exists()

        if already:
            user.refresh_from_db()
            return cls.summary(user)

        with transaction.atomic():
            user_locked = User.objects.select_for_update().get(pk=user.pk)
            cls._update_streak(user_locked, today)
            ActivityLog.objects.create(
                user=user_locked,
                activity_type=ActivityLog.ActivityType.DAILY_SESSION,
                delta_points=DAILY_SESSION_POINTS,
            )
            user_locked.points += DAILY_SESSION_POINTS

            streak_bonus = False
            if user_locked.streak >= 2:
                ActivityLog.objects.create(
                    user=user_locked,
                    activity_type=ActivityLog.ActivityType.STREAK_BONUS,
                    delta_points=STREAK_BONUS_POINTS,
                )
                user_locked.points += STREAK_BONUS_POINTS
                streak_bonus = True

            cls._apply_level_rules(user_locked)
            cls._update_monthly_reward(user_locked)
            user_locked.save(
                update_fields=[
                    "points",
                    "level",
                    "streak",
                    "longest_streak",
                    "last_streak_date",
                    "monthly_reward_unlocked",
                ],
            )

        logger.debug(
            "Recorded session user=%s streak_bonus=%s points=%s level=%s",
            user.pk,
            streak_bonus,
            user_locked.points,
            user_locked.level,
        )
        return cls.summary(user_locked)

    @staticmethod
    def summary(user: User) -> dict:
        monthly_points = GamificationService._monthly_points_total(user)
        return {
            "points": user.points,
            "level": user.level,
            "streak": user.streak,
            "longest_streak": user.longest_streak,
            "last_streak_date": user.last_streak_date,
            "monthly_reward_unlocked": user.monthly_reward_unlocked,
            "monthly_points_this_month": monthly_points,
        }

    @staticmethod
    def recent_activity(user: User, limit: int = 50):
        return ActivityLog.objects.filter(user=user).order_by("-created_at")[:limit]
