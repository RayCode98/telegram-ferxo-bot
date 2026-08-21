from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ModerationAction, User, UserRestriction
from app.redis_client import redis


async def _fixed_window_limit(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = await pipe.execute()

    if ttl == -1:
        await redis.expire(key, window_seconds)
        ttl = window_seconds

    return int(count) <= limit, max(int(ttl), 1)


async def chat_message_allowed(telegram_id: int) -> tuple[bool, int]:
    mute_ttl = await redis.ttl(f"security:mute:{telegram_id}")
    if mute_ttl and mute_ttl > 0:
        return False, int(mute_ttl)

    ok, ttl = await _fixed_window_limit(
        f"security:chat:{telegram_id}",
        settings.chat_messages_limit,
        settings.chat_messages_window_seconds,
    )
    if ok:
        return True, 0

    strikes_key = f"security:flood_strikes:{telegram_id}"
    strikes = int(await redis.incr(strikes_key))
    await redis.expire(strikes_key, 3600)

    mute_seconds = 30 if strikes <= 2 else 300
    await redis.set(
        f"security:mute:{telegram_id}",
        "1",
        ex=mute_seconds,
    )
    return False, mute_seconds


async def next_allowed(telegram_id: int) -> tuple[bool, int]:
    return await _fixed_window_limit(
        f"security:next:{telegram_id}",
        settings.next_limit,
        settings.next_window_seconds,
    )


async def search_allowed(telegram_id: int) -> tuple[bool, int]:
    return await _fixed_window_limit(
        f"security:search:{telegram_id}",
        settings.search_burst_limit,
        settings.search_burst_window_seconds,
    )


async def report_allowed(telegram_id: int) -> tuple[bool, int]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return await _fixed_window_limit(
        f"security:report:{today}:{telegram_id}",
        settings.report_daily_limit,
        172800,
    )


async def get_active_restriction(
    session: AsyncSession,
    user: User,
) -> UserRestriction | None:
    if user.is_banned:
        return UserRestriction(
            user_id=user.id,
            restriction_type="ban",
            reason="Bloqueo permanente",
            active=True,
        )

    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(UserRestriction)
        .where(
            UserRestriction.user_id == user.id,
            UserRestriction.active.is_(True),
        )
        .order_by(UserRestriction.created_at.desc())
    )

    for restriction in result.scalars():
        if restriction.expires_at is None or restriction.expires_at > now:
            return restriction

        restriction.active = False

    await session.commit()
    return None


async def apply_restriction(
    session: AsyncSession,
    user: User,
    *,
    admin_telegram_id: int | None,
    reason: str,
    expires_at=None,
    permanent: bool = False,
) -> UserRestriction:
    if permanent:
        user.is_banned = True

    restriction = UserRestriction(
        user_id=user.id,
        restriction_type="ban",
        reason=reason[:255],
        expires_at=None if permanent else expires_at,
        active=True,
        created_by_telegram_id=admin_telegram_id,
    )
    session.add(restriction)
    session.add(
        ModerationAction(
            target_user_id=user.id,
            admin_telegram_id=admin_telegram_id,
            action="ban_permanent" if permanent else "ban_temporary",
            reason=reason[:255],
            expires_at=None if permanent else expires_at,
        )
    )
    await session.commit()
    return restriction


async def lift_restrictions(
    session: AsyncSession,
    user: User,
    admin_telegram_id: int | None,
) -> None:
    user.is_banned = False

    result = await session.execute(
        select(UserRestriction).where(
            UserRestriction.user_id == user.id,
            UserRestriction.active.is_(True),
        )
    )
    for restriction in result.scalars():
        restriction.active = False

    session.add(
        ModerationAction(
            target_user_id=user.id,
            admin_telegram_id=admin_telegram_id,
            action="unban",
            reason="Restricciones retiradas",
        )
    )
    await session.commit()


def restriction_text(restriction: UserRestriction) -> str:
    if restriction.expires_at:
        expiry = restriction.expires_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        return (
            "⛔ <b>Tu acceso a FreXo está restringido temporalmente.</b>\n\n"
            f"Motivo: {restriction.reason or 'Moderación'}\n"
            f"Finaliza: {expiry}"
        )

    return (
        "⛔ <b>Tu acceso a FreXo está restringido.</b>\n\n"
        f"Motivo: {restriction.reason or 'Moderación'}"
    )
