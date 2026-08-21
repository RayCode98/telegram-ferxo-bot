from __future__ import annotations

from datetime import datetime, timedelta, timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ExperiencePreference, User
from app.redis_client import redis
from app.repositories import are_blocked
from app.services.compatibility import compatibility_details
from app.services.matchmaking import base_compatible, get_active_partner, is_searching, haversine_km
from app.services.growth import active_travel_country, get_growth_profile


async def notify_compatible_users(bot: Bot, session: AsyncSession, newcomer: User, *, mode: str="global", limit: int=3) -> int:
    result=await session.execute(
        select(User)
        .join(ExperiencePreference, ExperiencePreference.user_id==User.id)
        .where(
            User.id != newcomer.id,
            User.onboarding_completed.is_(True),
            User.is_banned.is_(False),
            ExperiencePreference.smart_notifications.is_(True),
            User.last_seen_at >= datetime.now(timezone.utc)-timedelta(days=30),
        )
        .order_by(User.last_seen_at.desc()).limit(80)
    )
    newcomer_growth = await get_growth_profile(session, newcomer)
    newcomer_travel = active_travel_country(newcomer_growth)
    candidates=[]
    for candidate in result.scalars():
        if not base_compatible(newcomer,candidate): continue
        candidate_growth = await get_growth_profile(session, candidate)
        candidate_travel = active_travel_country(candidate_growth)
        if newcomer_travel and candidate_growth.home_country_code != newcomer_travel: continue
        if candidate_travel and newcomer_growth.home_country_code != candidate_travel: continue
        if mode == "nearby":
            distance = haversine_km(newcomer, candidate)
            if distance is None or distance > newcomer.max_distance_km: continue
        if await are_blocked(session,newcomer,candidate): continue
        if await get_active_partner(candidate.telegram_id) or await is_searching(candidate.telegram_id): continue
        pair_key=f"smartnotify:pair:{candidate.telegram_id}:{newcomer.telegram_id}"
        if await redis.exists(pair_key): continue
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        daily_key=f"smartnotify:daily:{day}:{candidate.telegram_id}"
        if int(await redis.get(daily_key) or 0)>=2: continue
        score,_=await compatibility_details(session,candidate,newcomer)
        if score>=60: candidates.append((score,candidate))
    candidates.sort(key=lambda x:x[0], reverse=True)
    sent=0
    for score,candidate in candidates[:limit]:
        keyboard=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Buscar ahora", callback_data="smart:search")],
            [InlineKeyboardButton(text="🔕 Desactivar estos avisos", callback_data="smart:disable")],
        ])
        try:
            await bot.send_message(candidate.telegram_id, f"🔔 <b>Hay alguien compatible disponible en FreXo.</b>\n\n💞 Compatibilidad estimada: <b>{score}%</b>\n\nSi te interesa conocer a alguien ahora, vuelve a la búsqueda.", reply_markup=keyboard)
        except Exception:
            continue
        await redis.set(f"smartnotify:pair:{candidate.telegram_id}:{newcomer.telegram_id}","1",ex=21600)
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d'); daily_key=f"smartnotify:daily:{day}:{candidate.telegram_id}"
        pipe=redis.pipeline(); pipe.incr(daily_key); pipe.expire(daily_key,172800); await pipe.execute(); sent+=1
    return sent
