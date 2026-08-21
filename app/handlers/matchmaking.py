from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import active_chat_keyboard, search_cancel_keyboard
from app.repositories import get_user_by_telegram
from app.services.matchmaking import (
    can_search,
    dequeue,
    get_active_partner,
    try_match,
)
from app.services.profile import send_profile_card
from app.services.security import get_active_restriction, restriction_text, search_allowed


router = Router(name="matchmaking")


async def begin_search(message: Message, mode: str) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user or not user.onboarding_completed:
            await message.answer("Primero usa /start para completar tu perfil.")
            return
        restriction = await get_active_restriction(session, user)
        if restriction:
            await message.answer(restriction_text(restriction))
            return

        burst_ok, burst_ttl = await search_allowed(user.telegram_id)
        if not burst_ok:
            await message.answer(
                f"⏳ Estás buscando demasiado rápido. Intenta de nuevo en "
                f"aproximadamente {burst_ttl} segundos."
            )
            return
        if await get_active_partner(user.telegram_id):
            await message.answer("Ya tienes una conversación activa.")
            return

        if mode == "nearby" and (
            user.latitude is None or user.longitude is None
        ):
            await message.answer(
                "📍 Para buscar cerca de ti primero comparte tu ubicación "
                "desde <b>⚙️ Preferencias</b>."
            )
            return

        allowed, remaining = await can_search(user)
        if not allowed:
            await message.answer(
                "⏳ Alcanzaste el límite gratuito de búsquedas de hoy.\n\n"
                "👑 Premium elimina este límite."
            )
            return

        result = await try_match(session, user, mode)
        if not result:
            extra = (
                f"\n\nTe quedan aproximadamente {remaining} búsquedas gratuitas hoy."
                if remaining
                else ""
            )
            await message.answer(
                "🔎 <b>Buscando una persona compatible…</b>\n"
                "Te avisaré cuando aparezca alguien."
                + extra,
                reply_markup=search_cancel_keyboard(),
            )
            return

        partner, _conversation_id = result
        await message.answer(
            "🤖 <b>FreXo</b>\n\n🎉 <b>¡Encontramos a alguien!</b>\n\n"
            "Ya pueden comenzar a conversar. Su identidad de Telegram "
            "permanece oculta."
        )
        await send_profile_card(
            message.bot,
            message.from_user.id,
            partner,
            viewer=user,
            reply_markup=active_chat_keyboard(),
        )

        await message.bot.send_message(
            partner.telegram_id,
            "🤖 <b>FreXo</b>\n\n🎉 <b>¡Encontramos a alguien!</b>\n\n"
            "Ya pueden comenzar a conversar. Su identidad de Telegram "
            "permanece oculta."
        )
        await send_profile_card(
            message.bot,
            partner.telegram_id,
            user,
            viewer=partner,
            reply_markup=active_chat_keyboard(),
        )


@router.message(F.text == "🎲 Buscar persona")
async def search_global(message: Message) -> None:
    await begin_search(message, "global")


@router.message(F.text == "📍 Personas cerca")
async def search_nearby(message: Message) -> None:
    await begin_search(message, "nearby")


@router.callback_query(F.data == "search:cancel")
async def cancel_search(callback: CallbackQuery) -> None:
    await dequeue(callback.from_user.id)
    await callback.answer("Búsqueda cancelada")
    await callback.message.edit_text("❌ Búsqueda cancelada.")
