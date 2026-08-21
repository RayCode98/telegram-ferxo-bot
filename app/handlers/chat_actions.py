from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.types import Message

from app.database import SessionLocal
from app.keyboards import (
    gift_keyboard,
    main_menu,
    reconnect_after_chat_keyboard,
    report_keyboard,
)
from app.models import Conversation
from app.repositories import (
    add_block,
    add_interest,
    consume,
    end_conversation,
    get_balance,
    get_user_by_telegram,
    profile_reveal_is_mutual,
    set_contact_share_consent,
    set_profile_reveal_consent,
)
from app.services.conversation_ui import (
    close_chat_panel,
    ensure_chat_panel,
    refresh_pair_panels,
    set_chat_keyboard_page,
)
from app.services.matchmaking import (
    clear_active_pair,
    get_active_partner,
)
from app.services.profile import send_profile_card
from app.services.quality import suggestion_for_pair
from app.services.security import next_allowed
from app.services.social_graph import add_favorite


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

    user = await get_user_by_telegram(
        session,
        message.from_user.id,
    )
    partner = await get_user_by_telegram(
        session,
        partner_tg,
    )
    conversation = await session.get(
        Conversation,
        conversation_id,
    )

    if not user or not partner or not conversation:
        await session.close()
        return None

    return session, user, partner, conversation


@router.message(F.text == "➡️ Más opciones")
async def more_actions(message: Message) -> None:
    if not await get_active_partner(message.from_user.id):
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    await set_chat_keyboard_page(
        message.bot,
        message.from_user.id,
        2,
    )


@router.message(F.text == "⬅️ Acciones principales")
async def primary_actions(message: Message) -> None:
    if not await get_active_partner(message.from_user.id):
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    await set_chat_keyboard_page(
        message.bot,
        message.from_user.id,
        1,
    )


@router.message(F.text == "🧭 Panel de chat")
async def reopen_panel(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        await ensure_chat_panel(
            message.bot,
            session,
            user,
            partner,
            conversation.id,
        )
        await message.answer("📌 Panel actualizado.")
    finally:
        await session.close()


@router.message(F.text == "👤 Mi conexión")
async def connection_profile(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        reveal = await profile_reveal_is_mutual(
            session,
            conversation.id,
        )
        await send_profile_card(
            message.bot,
            message.from_user.id,
            partner,
            viewer=user,
            force_full=reveal,
            session=session,
        )
    finally:
        await session.close()


@router.message(F.text == "❤️ Me interesa")
async def quick_like(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        _, mutual = await add_interest(
            session,
            user,
            partner,
            conversation.id,
            False,
        )

        if mutual:
            await message.answer(
                "💘 <b>¡Hay interés mutuo!</b>"
            )
            await message.bot.send_message(
                partner.telegram_id,
                "💘 <b>¡Hay interés mutuo!</b>",
            )
        else:
            await message.answer("❤️ Interés guardado.")
    finally:
        await session.close()


@router.message(F.text == "👀 Conocer más")
async def quick_know_more(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        mutual = await set_profile_reveal_consent(
            session,
            conversation,
            user,
        )

        if not mutual:
            await message.answer(
                "👀 Solicitud guardada. El perfil ampliado sólo se revelará "
                "si tu conexión también acepta."
            )
            await message.bot.send_message(
                partner.telegram_id,
                "👀 <b>Tu conexión quiere conocerte mejor.</b>\n\n"
                "Pulsa «👀 Conocer más» si también quieres.",
            )
            return

        await message.answer(
            "🤝 <b>¡Ambos aceptaron conocerse mejor!</b>"
        )
        await message.bot.send_message(
            partner.telegram_id,
            "🤝 <b>¡Ambos aceptaron conocerse mejor!</b>",
        )
        await refresh_pair_panels(
            message.bot,
            session,
            user,
            partner,
            conversation.id,
        )
    finally:
        await session.close()


@router.message(F.text == "💘 Super Interés")
async def quick_super_interest(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        if await get_balance(
            session,
            user,
            "super_interest",
        ) < 1:
            await message.answer(
                "💘 No tienes Super Intereses. "
                "Puedes obtenerlos en la tienda."
            )
            return

        if not await consume(
            session,
            user,
            "super_interest",
            1,
        ):
            return

        _, mutual = await add_interest(
            session,
            user,
            partner,
            conversation.id,
            True,
        )

        await message.answer("💘 Super Interés enviado.")
        await message.bot.send_message(
            partner.telegram_id,
            "💘 <b>Tu conexión te envió un Super Interés.</b>",
        )

        if mutual:
            await message.answer(
                "❤️ Además, el interés ya es mutuo."
            )
    finally:
        await session.close()


@router.message(F.text == "📲 Compartir Telegram")
async def quick_share_contact(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        if not await profile_reveal_is_mutual(
            session,
            conversation.id,
        ):
            await message.answer(
                "🤝 Primero ambos deben aceptar «Conocer más»."
            )
            return

        mutual = await set_contact_share_consent(
            session,
            conversation,
            user,
        )

        if not mutual:
            await message.answer(
                "📲 Aceptaste compartir tu Telegram. "
                "No se revelará hasta que tu conexión también acepte."
            )
            await message.bot.send_message(
                partner.telegram_id,
                "📲 Tu conexión está dispuesta a compartir su Telegram. "
                "Usa «📲 Compartir Telegram» si tú también quieres.",
            )
            return

        user_link = (
            f'<a href="tg://user?id={user.telegram_id}">'
            f'{escape(user.alias or "Abrir perfil")}</a>'
        )
        partner_link = (
            f'<a href="tg://user?id={partner.telegram_id}">'
            f'{escape(partner.alias or "Abrir perfil")}</a>'
        )

        await message.answer(
            "🤝 <b>Ambos aceptaron compartir su Telegram.</b>\n\n"
            f"📲 {partner_link}"
        )
        await message.bot.send_message(
            partner.telegram_id,
            "🤝 <b>Ambos aceptaron compartir su Telegram.</b>\n\n"
            f"📲 {user_link}",
        )
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
        "🎁 <b>Elige un regalo:</b>",
        reply_markup=gift_keyboard(),
    )


@router.message(F.text == "⭐ Guardar favorito")
async def quick_favorite(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, _conversation = data
    try:
        created = await add_favorite(
            session,
            user,
            partner,
        )
        await message.answer(
            "⭐ Conexión guardada en Favoritos."
            if created
            else "⭐ Esta conexión ya estaba en Favoritos."
        )
    finally:
        await session.close()


@router.message(F.text == "🚨 Reportar")
async def quick_report(message: Message) -> None:
    if not await get_active_partner(message.from_user.id):
        await message.answer(
            "No tienes una conversación activa.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        "🚨 <b>¿Qué ocurrió?</b>",
        reply_markup=report_keyboard(),
    )


@router.message(F.text == "🚫 Bloquear")
async def quick_block(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        await add_block(
            session,
            user,
            partner,
        )
        await end_conversation(
            session,
            conversation.id,
            user.id,
            "blocked",
        )
    finally:
        await session.close()

    await clear_active_pair(
        user.telegram_id,
        partner.telegram_id,
    )

    await close_chat_panel(
        message.bot,
        user.telegram_id,
        reason="Usuario bloqueado.",
        notice=(
            "🚫 Bloqueaste a esta conexión. "
            "No volverán a ser emparejados."
        ),
        conversation_id=conversation.id,
        ask_feedback=False,
    )
    await close_chat_panel(
        message.bot,
        partner.telegram_id,
        reason="La conversación terminó.",
        notice=(
            "👋 <b>La conversación terminó.</b>\n\n"
            "Esta conexión ya no está disponible."
        ),
        conversation_id=conversation.id,
        ask_feedback=False,
    )


@router.message(F.text == "💡 Sugerencia")
async def quick_suggestion(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, _conversation = data
    try:
        suggestion = await suggestion_for_pair(
            session,
            user,
            partner,
        )
    finally:
        await session.close()

    await message.answer(
        "💡 <b>Idea para continuar la conversación</b>\n\n"
        f"{suggestion}\n\n"
        "<i>La sugerencia sólo la ves tú.</i>"
    )


@router.message(F.text == "❌ Terminar")
async def quick_end(message: Message) -> None:
    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        await end_conversation(
            session,
            conversation.id,
            user.id,
            "ended",
        )
    finally:
        await session.close()

    await clear_active_pair(
        user.telegram_id,
        partner.telegram_id,
    )

    await close_chat_panel(
        message.bot,
        user.telegram_id,
        reason="Conversación terminada.",
        notice="👋 Terminaste la conversación.",
        conversation_id=conversation.id,
        ask_feedback=True,
    )
    await close_chat_panel(
        message.bot,
        partner.telegram_id,
        reason="Tu conexión terminó la conversación.",
        notice=(
            "👋 <b>Tu conexión terminó la conversación.</b>\n\n"
            "Ya puedes buscar otra persona cuando quieras."
        ),
        conversation_id=conversation.id,
        ask_feedback=True,
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
            f"Espera {ttl} segundos."
        )
        return

    data = await _active_users(message)
    if not data:
        return

    session, user, partner, conversation = data
    try:
        await end_conversation(
            session,
            conversation.id,
            user.id,
            "next",
        )
    finally:
        await session.close()

    await clear_active_pair(
        user.telegram_id,
        partner.telegram_id,
    )

    await close_chat_panel(
        message.bot,
        user.telegram_id,
        reason="Pasaste a la siguiente persona.",
        notice=(
            "🔄 Cerraste esta conversación para buscar otra conexión."
        ),
        conversation_id=conversation.id,
        ask_feedback=True,
    )
    await close_chat_panel(
        message.bot,
        partner.telegram_id,
        reason="Tu conexión decidió buscar otra persona.",
        notice=(
            "🔄 <b>Tu conexión decidió buscar otra persona.</b>\n\n"
            "La conversación terminó y ya puedes iniciar otra búsqueda."
        ),
        conversation_id=conversation.id,
        ask_feedback=True,
    )

    await message.answer(
        "🔄 Puedes usar 🎲 Buscar persona cuando quieras continuar.",
        reply_markup=reconnect_after_chat_keyboard(),
    )
