from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WeeklyProgress
from app.repositories import add_consumable
from app.services.analytics import track_event


MATCH_GOAL = 3
MESSAGE_GOAL = 25
DAILY_GOAL = 3


def current_week_key() -> str:
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def get_weekly_progress(
    session: AsyncSession,
    user: User,
) -> WeeklyProgress:
    week_key = current_week_key()
    result = await session.execute(
        select(WeeklyProgress).where(
            WeeklyProgress.user_id == user.id,
            WeeklyProgress.week_key == week_key,
        )
    )
    progress = result.scalar_one_or_none()
    if progress:
        return progress

    progress = WeeklyProgress(
        user_id=user.id,
        week_key=week_key,
    )
    session.add(progress)
    await session.flush()
    return progress


async def record_weekly_event(
    session: AsyncSession,
    user: User,
    event: str,
    amount: int = 1,
) -> None:
    progress = await get_weekly_progress(session, user)

    if event == "match":
        progress.matches_count += amount
    elif event == "message":
        progress.messages_count += amount
    elif event == "daily":
        progress.daily_claims_count += amount
    else:
        return

    await session.flush()


@dataclass
class WeeklyStatus:
    progress: WeeklyProgress
    matches_ready: bool
    messages_ready: bool
    daily_ready: bool
    bonus_ready: bool


async def weekly_status(
    session: AsyncSession,
    user: User,
) -> WeeklyStatus:
    p = await get_weekly_progress(session, user)

    matches_ready = (
        p.matches_count >= MATCH_GOAL
        and not p.matches_reward_claimed
    )
    messages_ready = (
        p.messages_count >= MESSAGE_GOAL
        and not p.messages_reward_claimed
    )
    daily_ready = (
        p.daily_claims_count >= DAILY_GOAL
        and not p.daily_reward_claimed
    )
    bonus_ready = (
        p.matches_reward_claimed
        and p.messages_reward_claimed
        and p.daily_reward_claimed
        and not p.bonus_reward_claimed
    )

    return WeeklyStatus(
        progress=p,
        matches_ready=matches_ready,
        messages_ready=messages_ready,
        daily_ready=daily_ready,
        bonus_ready=bonus_ready,
    )


async def claim_weekly_reward(
    session: AsyncSession,
    user: User,
    mission: str,
) -> tuple[bool, str]:
    p = await get_weekly_progress(session, user)

    if mission == "matches":
        if p.matches_count < MATCH_GOAL or p.matches_reward_claimed:
            return False, "Esta misión todavía no puede reclamarse."
        p.matches_reward_claimed = True
        await add_consumable(session, user, "super_interest", 2)
        reward = "💘 2 Super Intereses"

    elif mission == "messages":
        if p.messages_count < MESSAGE_GOAL or p.messages_reward_claimed:
            return False, "Esta misión todavía no puede reclamarse."
        p.messages_reward_claimed = True
        await add_consumable(session, user, "boost_30m_credit", 1)
        reward = "🚀 1 Boost de 30 min"

    elif mission == "daily":
        if p.daily_claims_count < DAILY_GOAL or p.daily_reward_claimed:
            return False, "Esta misión todavía no puede reclamarse."
        p.daily_reward_claimed = True
        await add_consumable(session, user, "travel_pass", 1)
        reward = "🌎 1 Travel Pass"

    elif mission == "bonus":
        if not (
            p.matches_reward_claimed
            and p.messages_reward_claimed
            and p.daily_reward_claimed
        ) or p.bonus_reward_claimed:
            return False, "Completa y reclama primero las tres misiones."
        p.bonus_reward_claimed = True
        await add_consumable(session, user, "spotlight_3h", 1)
        reward = "🔥 1 Spotlight de 3 h"

    else:
        return False, "Misión no válida."

    await track_event(
        session,
        user,
        "weekly_reward_claimed",
        {"mission": mission, "week": p.week_key},
    )
    await session.commit()
    return True, reward
