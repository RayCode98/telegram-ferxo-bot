from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import Message

from app.database import SessionLocal
from app.keyboards import location_keyboard, main_menu
from app.repositories import get_user_by_telegram
from app.services.matchmaking import age_of


router = Router(name="profile")


def gender_label(value: str | None) -> str:
    return {
        "male": "Hombre",
        "female": "Mujer",
        "other": "Otro",
        "any": "Cualquiera",
    }.get(value, "Sin definir")


@router.message(F.text == "👤 Mi perfil")
async def my_profile(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        premium = bool(
            user.premium_until and user.premium_until > datetime.now(timezone.utc)
        )
        location = "✅ Configurada" if user.latitude is not None else "❌ No configurada"

        await message.answer(
            f"👤 <b>{user.alias or 'Sin alias'}</b>\n"
            f"🎂 {age_of(user.birth_date) or '?'} años\n"
            f"🚻 {gender_label(user.gender)}\n"
            f"❤️ Busca: {gender_label(user.seeking_gender)}\n"
            f"📍 Ubicación: {location}\n"
            f"🎯 Edad: {user.min_age}–{user.max_age}\n"
            f"👑 Premium: {'Sí' if premium else 'No'}\n\n"
            "Envía una ubicación nueva en cualquier momento desde "
            "<b>⚙️ Preferencias</b>."
        )


@router.message(F.text == "⚙️ Preferencias")
async def preferences(message: Message) -> None:
    await message.answer(
        "⚙️ <b>Preferencias actuales</b>\n\n"
        "En esta primera versión puedes actualizar tu ubicación con el botón "
        "de abajo. Los controles detallados de rango de edad, distancia y país "
        "quedan preparados para la siguiente iteración.",
        reply_markup=location_keyboard(),
    )


@router.message(F.location)
async def update_location(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user or not user.onboarding_completed:
            return
        user.latitude = message.location.latitude
        user.longitude = message.location.longitude
        user.location_updated_at = datetime.now(timezone.utc)
        await session.commit()

    await message.answer(
        "📍 Ubicación actualizada. Nunca se mostrará tu coordenada exacta.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "🛡️ Seguridad")
async def safety(message: Message) -> None:
    await message.answer(
        "🛡️ <b>Seguridad en FreXo</b>\n\n"
        "• No compartimos tu Telegram automáticamente.\n"
        "• Tu ubicación exacta nunca se muestra a otra persona.\n"
        "• Puedes terminar, bloquear o reportar una conversación.\n"
        "• Un pago nunca permite saltarse un bloqueo ni el consentimiento.\n"
        "• Si alguien te solicita datos sensibles, termina y reporta."
    )
