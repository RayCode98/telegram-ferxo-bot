from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.redis_client import redis
from app.services.social_graph import mark_active, get_experience_preferences


class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user and not from_user.is_bot:
            telegram_id = int(from_user.id)
            await mark_active(telegram_id)
            first_touch = await redis.set(f"presence:dbtouch:{telegram_id}", "1", ex=300, nx=True)
            if first_touch:
                async with SessionLocal() as session:
                    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                    user = result.scalar_one_or_none()
                    if user:
                        user.last_seen_at = datetime.now(timezone.utc)
                        await session.commit()
                        await get_experience_preferences(session, user)
        return await handler(event, data)
