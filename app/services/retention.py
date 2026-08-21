from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RetentionProfile, User
from app.redis_client import redis
from app.repositories import add_consumable
from app.services.analytics import track_event


CLAIM_INTERVAL = timedelta(hours=20)
STREAK_GRACE = timedelta(hours=48)

REWARD_CYCLE = {
    1: ("super_interest", 1, "💘 1 Super Interés"),
    2: ("super_interest", 1, "💘 1 Super Interés"),
    3: ("boost_30m_credit", 1, "🚀 1 Boost de 30 min"),
    4: ("super_interest", 2, "💘 2 Super Intereses"),
    5: ("travel_pass", 1, "🌎 1 Travel Pass"),
    6: ("super_interest", 2, "💘 2 Super Intereses"),
    7: ("spotlight_3h", 1, "🔥 1 Spotlight de 3 h"),
}


@dataclass
class DailyRewardStatus:
    can_claim: bool
    streak: int
    longest_streak: int
    next_claim_at: datetime | None
    next_reward_label: str


async def get_retention_profile(
    session: AsyncSession,
    user: User,
) -> RetentionProfile:
    result = await session.execute(
        select(RetentionProfile).where(RetentionProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    profile = RetentionProfile(user_id=user.id)
    session.add(profile)
    await session.flush()
    return profile


def _cycle_day(streak: int) -> int:
    return ((max(streak, 0)) % 7) + 1


async def daily_status(
    session: AsyncSession,
    user: User,
) -> DailyRewardStatus:
    profile = await get_retention_profile(session, user)
    now = datetime.now(timezone.utc)

    if profile.last_daily_claim_at is None:
        can_claim = True
        next_claim = None
    else:
        next_claim = profile.last_daily_claim_at + CLAIM_INTERVAL
        can_claim = now >= next_claim

    day = _cycle_day(profile.streak_count)
    return DailyRewardStatus(
        can_claim=can_claim,
        streak=profile.streak_count,
        longest_streak=profile.longest_streak,
        next_claim_at=next_claim,
        next_reward_label=REWARD_CYCLE[day][2],
    )


async def claim_daily_reward(
    session: AsyncSession,
    user: User,
) -> tuple[bool, str, RetentionProfile]:
    lock = redis.lock(
        f"retention:daily:{user.telegram_id}",
        timeout=8,
        blocking_timeout=3,
    )

    async with lock:
        profile = await get_retention_profile(session, user)
        now = datetime.now(timezone.utc)

        if (
            profile.last_daily_claim_at
            and now < profile.last_daily_claim_at + CLAIM_INTERVAL
        ):
            remaining = (
                profile.last_daily_claim_at + CLAIM_INTERVAL - now
            )
            hours = max(1, int(remaining.total_seconds() // 3600) + 1)
            return (
                False,
                f"Tu próxima recompensa estará disponible en aproximadamente {hours} h.",
                profile,
            )

        if (
            profile.last_daily_claim_at
            and now - profile.last_daily_claim_at <= STREAK_GRACE
        ):
            profile.streak_count += 1
        else:
            profile.streak_count = 1

        profile.longest_streak = max(
            profile.longest_streak,
            profile.streak_count,
        )
        profile.last_daily_claim_at = now
        profile.total_daily_claims += 1

        day = ((profile.streak_count - 1) % 7) + 1
        code, amount, label = REWARD_CYCLE[day]
        await add_consumable(session, user, code, amount)

        await track_event(
            session,
            user,
            "daily_reward_claimed",
            {
                "streak": profile.streak_count,
                "cycle_day": day,
                "reward": code,
                "amount": amount,
            },
        )
        await session.commit()
        return True, label, profile
