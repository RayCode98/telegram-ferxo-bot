from __future__ import annotations

from datetime import datetime, timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import SessionLocal
from app.models import User
from app.services.compatibility import compatibility_text
from app.services.matchmaking import age_of, haversine_km
from app.services.social_graph import activity_label, interest_codes, interest_labels


def gender_label(value: str | None) -> str:
    return {"male":"Hombre","female":"Mujer","other":"Otro","any":"Cualquiera"}.get(value,"Sin definir")


def approximate_distance_text(viewer: User, profile: User) -> str:
    distance = haversine_km(viewer, profile)
    if distance is None: return "No disponible"
    if distance < 1: return "A menos de 1 km"
    if distance < 5: return "A unos pocos kilómetros"
    if distance < 10: return "A menos de 10 km"
    if distance < 25: return "A menos de 25 km"
    if distance < 50: return "A menos de 50 km"
    if distance < 100: return "A menos de 100 km"
    return "A más de 100 km"


def premium_active(user: User) -> bool:
    return bool(user.premium_until and user.premium_until > datetime.now(timezone.utc))


async def _caption(session: AsyncSession, profile: User, viewer: User | None, full: bool) -> str:
    age=age_of(profile.birth_date) or "?"
    lines=[f"👤 <b>{profile.alias or 'Sin alias'}</b>", f"🎂 {age} años", f"🚻 {gender_label(profile.gender)}"]
    if viewer is not None and viewer.id != profile.id:
        lines += [await activity_label(session, profile), await compatibility_text(session, viewer, profile)]
    codes=await interest_codes(session, profile)
    if codes:
        lines.append("🎯 " + " · ".join(interest_labels(codes)[:6]))
    if full and viewer is not None:
        lines.append(f"📍 {approximate_distance_text(viewer, profile)}")
    if full and profile.bio:
        lines += ["", f"📝 {profile.bio}"]
    if not full and viewer is not None and viewer.id != profile.id:
        lines += ["", "👑 Premium muestra foto, bio y distancia desde el inicio.", "🤝 «Conocer más» desbloquea el perfil ampliado si ambos aceptan."]
    if viewer is not None and viewer.id != profile.id:
        lines += ["", "🔒 Su usuario, teléfono e ID de Telegram permanecen ocultos."]
    return "\n".join(lines)


async def send_profile_card(bot: Bot, chat_id: int, profile: User, viewer: User | None = None, reply_markup: InlineKeyboardMarkup | None = None, *, force_full: bool = False, session: AsyncSession | None = None) -> None:
    own_session = session is None
    if own_session:
        session = SessionLocal()
    try:
        full = force_full or viewer is None or (viewer is not None and premium_active(viewer))
        caption = await _caption(session, profile, viewer, full)
        if full and profile.photo_file_id:
            await bot.send_photo(chat_id=chat_id, photo=profile.photo_file_id, caption=caption, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)
    finally:
        if own_session:
            await session.close()
