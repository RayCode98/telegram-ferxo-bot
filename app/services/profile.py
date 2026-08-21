from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from app.models import User
from app.services.matchmaking import age_of, haversine_km


def gender_label(value: str | None) -> str:
    return {
        "male": "Hombre",
        "female": "Mujer",
        "other": "Otro",
        "any": "Cualquiera",
    }.get(value, "Sin definir")


def approximate_distance_text(viewer: User, profile: User) -> str:
    distance = haversine_km(viewer, profile)
    if distance is None:
        return "No disponible"

    if distance < 1:
        return "A menos de 1 km"
    if distance < 5:
        return "A unos pocos kilómetros"
    if distance < 10:
        return "A menos de 10 km"
    if distance < 25:
        return "A menos de 25 km"
    if distance < 50:
        return "A menos de 50 km"
    if distance < 100:
        return "A menos de 100 km"
    return "A más de 100 km"


def profile_caption(profile: User, viewer: User | None = None) -> str:
    age = age_of(profile.birth_date) or "?"
    lines = [
        f"👤 <b>{profile.alias or 'Sin alias'}</b>",
        f"🎂 {age} años",
        f"🚻 {gender_label(profile.gender)}",
    ]

    if viewer is not None:
        lines.append(f"📍 {approximate_distance_text(viewer, profile)}")

    if profile.bio:
        lines.extend(["", f"📝 {profile.bio}"])

    lines.extend(
        [
            "",
            "🔒 Su usuario, teléfono e ID de Telegram permanecen ocultos.",
        ]
    )
    return "\n".join(lines)


async def send_profile_card(
    bot: Bot,
    chat_id: int,
    profile: User,
    viewer: User | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    caption = profile_caption(profile, viewer)

    if profile.photo_file_id:
        await bot.send_photo(
            chat_id=chat_id,
            photo=profile.photo_file_id,
            caption=caption,
            reply_markup=reply_markup,
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
        )


def premium_active(user: User) -> bool:
    return bool(
        user.premium_until
        and user.premium_until > datetime.now(timezone.utc)
    )
