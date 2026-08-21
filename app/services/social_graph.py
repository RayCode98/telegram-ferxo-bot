from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import INTEREST_LABELS
from app.models import ExperiencePreference, Favorite, User, UserInterest
from app.redis_client import redis

MAX_INTERESTS = 6
PRESENCE_TTL_SECONDS = 600


async def get_experience_preferences(session: AsyncSession, user: User) -> ExperiencePreference:
    result = await session.execute(
        select(ExperiencePreference).where(ExperiencePreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    prefs = ExperiencePreference(user_id=user.id)
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return prefs


async def toggle_activity_visibility(session: AsyncSession, user: User) -> bool:
    prefs = await get_experience_preferences(session, user)
    prefs.show_activity_status = not prefs.show_activity_status
    await session.commit()
    return prefs.show_activity_status


async def toggle_smart_notifications(session: AsyncSession, user: User) -> bool:
    prefs = await get_experience_preferences(session, user)
    prefs.smart_notifications = not prefs.smart_notifications
    await session.commit()
    return prefs.smart_notifications


async def mark_active(telegram_id: int) -> None:
    await redis.set(f"presence:active:{telegram_id}", "1", ex=PRESENCE_TTL_SECONDS)


async def is_active_recently(telegram_id: int) -> bool:
    return bool(await redis.exists(f"presence:active:{telegram_id}"))


async def activity_label(session: AsyncSession, user: User) -> str:
    prefs = await get_experience_preferences(session, user)
    if not prefs.show_activity_status:
        return "⚪ Actividad oculta"
    if await is_active_recently(user.telegram_id):
        return "🟢 Activo recientemente en FreXo"
    return "⚪ Sin actividad reciente en FreXo"


async def interest_codes(session: AsyncSession, user: User) -> set[str]:
    result = await session.execute(
        select(UserInterest.interest_code).where(UserInterest.user_id == user.id)
    )
    return set(result.scalars().all())


async def toggle_interest(session: AsyncSession, user: User, code: str) -> tuple[set[str], str | None]:
    selected = await interest_codes(session, user)
    if code not in INTEREST_LABELS:
        return selected, "Interés no válido."
    if code in selected:
        await session.execute(
            delete(UserInterest).where(
                UserInterest.user_id == user.id,
                UserInterest.interest_code == code,
            )
        )
        await session.commit()
        selected.remove(code)
        return selected, None
    if len(selected) >= MAX_INTERESTS:
        return selected, f"Puedes elegir hasta {MAX_INTERESTS} intereses."
    session.add(UserInterest(user_id=user.id, interest_code=code))
    await session.commit()
    selected.add(code)
    return selected, None


def interest_labels(codes: set[str]) -> list[str]:
    return [INTEREST_LABELS[c] for c in codes if c in INTEREST_LABELS]


async def common_interests(session: AsyncSession, a: User, b: User) -> set[str]:
    return (await interest_codes(session, a)) & (await interest_codes(session, b))


async def add_favorite(session: AsyncSession, user: User, target: User) -> bool:
    if user.id == target.id:
        return False
    result = await session.execute(
        select(Favorite.id).where(
            Favorite.user_id == user.id,
            Favorite.favorite_user_id == target.id,
        )
    )
    if result.scalar_one_or_none():
        return False
    session.add(Favorite(user_id=user.id, favorite_user_id=target.id))
    await session.commit()
    return True


async def remove_favorite(session: AsyncSession, user: User, target_user_id: str) -> bool:
    result = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.favorite_user_id == target_user_id,
        )
    )
    favorite = result.scalar_one_or_none()
    if not favorite:
        return False
    await session.delete(favorite)
    await session.commit()
    return True


async def favorite_users(session: AsyncSession, user: User, limit: int = 20) -> list[User]:
    result = await session.execute(
        select(User)
        .join(Favorite, Favorite.favorite_user_id == User.id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
