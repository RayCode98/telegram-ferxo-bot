from aiogram import F, Router
from aiogram.types import Message

from app.database import SessionLocal
from app.keyboards import (
    gift_keyboard,
    main_menu,
    reconnect_after_chat_keyboard,
)
from app.repositories import (
    add_interest,
    end_conversation,
    get_user_by_telegram,
    profile_reveal_is_mutual,
)
from app.services.conversation_ui import (
    close_chat_panel,
    ensure_chat_panel,
)
from app.services.matchmaking import (
    clear_active_pair,
    get_active_partner,
)
from app.services.profile import send_profile_card
from app.services.security import next_allowed


router = Router(name="chat_actions")


async def _active_users(message: Message):
    active = await get_active_partner(message.from_user.id)
    if not active:
        await message.answer(
            "🤖 <b>FreXo</b>\n\nNo tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return None

    partner_tg, conversation_id = active
    session = SessionLocal()
    user = await get_user_by_telegram(session, message.from_user.id)
    partner = await get_user_by_telegram(session, partner_tg)
    if not user or not partner:
        await session.close()
        return None

    return session, user, partner, conversation_id


@router.message(F.text == "🧭 Panel de chat")
async def reopen_panel(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation_id = data
    try:
        await ensure_chat_panel(
            message.bot,
            session,
            user,
            partner,
            conversation_id,
        )
        await message.answer(
            "📌 Panel actualizado y disponible en la parte superior."
        )
    finally:
        await session.close()


@router.message(F.text == "👤 Mi conexión")
async def connection_profile(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation_id = data
    try:
        reveal = await profile_reveal_is_mutual(
            session,
            conversation_id,
        )
        await send_profile_card(
            message.bot,
            message.from_user.id,
            partner,
            viewer=user,
            force_full=reveal,
        )
    finally:
        await session.close()


@router.message(F.text == "❤️ Me interesa")
async def quick_like(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation_id = data
    try:
        _, mutual = await add_interest(
            session,
            user,
            partner,
            conversation_id,
            False,
        )
        if mutual:
            await message.answer(
                "💘 <b>¡Hay interés mutuo!</b>"
            )
            await message.bot.send_message(
                partner.telegram_id,
                "💘 <b>¡Hay interés mutuo!</b>"
            )
        else:
            await message.answer("❤️ Interés guardado.")
    finally:
        await session.close()


@router.message(F.text == "🎁 Regalo")
async def quick_gift(message: Message) -> None:
    if not await get_active_partner(message.from_user.id):
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        "🎁 <b>Elige un regalo para tu conexión:</b>",
        reply_markup=gift_keyboard(),
    )


@router.message(F.text == "❌ Terminar")
async def quick_end(message: Message) -> None:
    active = await get_active_partner(message.from_user.id)
    if not active:
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    partner_tg, conversation_id = active
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        await end_conversation(
            session,
            conversation_id,
            user.id if user else None,
            "ended",
        )

    await clear_active_pair(message.from_user.id, partner_tg)
    await close_chat_panel(
        message.bot,
        message.from_user.id,
        reason="Conversación terminada.",
    )
    await close_chat_panel(
        message.bot,
        partner_tg,
        reason="La otra persona terminó la conversación.",
    )

    await message.answer(
        "↩️ Si cambiaste de opinión, puedes intentar reconectar.",
        reply_markup=reconnect_after_chat_keyboard(),
    )


@router.message(F.text == "🔄 Siguiente")
async def quick_next(message: Message) -> None:
    allowed, ttl = await next_allowed(message.from_user.id)
    if not allowed:
        await message.answer(
            f"⏳ Estás usando «Siguiente» demasiado rápido. "
            f"Espera aproximadamente {ttl} segundos."
        )
        return

    active = await get_active_partner(message.from_user.id)
    if not active:
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    partner_tg, conversation_id = active
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        await end_conversation(
            session,
            conversation_id,
            user.id if user else None,
            "next",
        )

    await clear_active_pair(message.from_user.id, partner_tg)
    await close_chat_panel(
        message.bot,
        message.from_user.id,
        reason="Pasaste a la siguiente persona.",
    )
    await close_chat_panel(
        message.bot,
        partner_tg,
        reason="La otra persona pasó a la siguiente conversación.",
    )

    await message.answer(
        "🔄 Conversación terminada.\n\n"
        "Pulsa <b>🎲 Buscar persona</b> cuando quieras continuar.",
        reply_markup=reconnect_after_chat_keyboard(),
    )
