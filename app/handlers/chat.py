from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import active_chat_keyboard, reconnect_after_chat_keyboard
from app.repositories import (
    add_interest,
    consume,
    end_conversation,
    get_balance,
    get_user_by_telegram,
    profile_reveal_is_mutual,
)
from app.services.chat import relay_message
from app.services.matchmaking import (
    clear_active_pair,
    get_active_partner,
)
from app.services.profile import send_profile_card
from app.services.conversation_ui import close_chat_panel, ensure_chat_panel
from app.services.security import chat_message_allowed, get_active_restriction, next_allowed, restriction_text


router = Router(name="chat")


async def finish_chat(
    callback: CallbackQuery,
    reason: str,
    notify_partner: bool = True,
) -> tuple[int, str] | None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay una conversación activa.", show_alert=True)
        return None

    partner_tg, conversation_id = active
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        await end_conversation(
            session,
            conversation_id,
            user.id if user else None,
            reason,
        )

    await clear_active_pair(callback.from_user.id, partner_tg)
    await close_chat_panel(
        callback.bot,
        callback.from_user.id,
        reason="Conversación finalizada.",
    )
    await close_chat_panel(
        callback.bot,
        partner_tg,
        reason="La otra persona terminó la conversación.",
    )

    if notify_partner:
        await callback.bot.send_message(
            partner_tg,
            "🤖 <b>FreXo</b>\n\n👋 La otra persona terminó la conversación.",
        )
    return partner_tg, conversation_id


@router.callback_query(F.data == "chat:end")
async def end_chat(callback: CallbackQuery) -> None:
    result = await finish_chat(callback, "ended")
    if result:
        await callback.answer()
        await callback.message.edit_text(
            "👋 Conversación terminada.",
            reply_markup=reconnect_after_chat_keyboard(),
        )


@router.callback_query(F.data == "chat:next")
async def next_chat(callback: CallbackQuery) -> None:
    allowed, ttl = await next_allowed(callback.from_user.id)
    if not allowed:
        await callback.answer(
            f"Estás usando «Siguiente» demasiado rápido. Espera {ttl} segundos.",
            show_alert=True,
        )
        return

    result = await finish_chat(callback, "next")
    if result:
        await callback.answer()
        await callback.message.edit_text(
            "🔄 Conversación terminada.\n\n"
            "Pulsa <b>🎲 Buscar persona</b> para encontrar otra, "
            "o intenta reconectar si cambiaste de opinión.",
            reply_markup=reconnect_after_chat_keyboard(),
        )





@router.callback_query(F.data == "chat:panel")
async def reopen_chat_panel_callback(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay conversación activa.", show_alert=True)
        return

    partner_tg, conversation_id = active
    async with SessionLocal() as session:
        viewer = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        if not viewer or not partner:
            return
        await ensure_chat_panel(
            callback.bot,
            session,
            viewer,
            partner,
            conversation_id,
        )

    await callback.answer("Panel actualizado")


@router.callback_query(F.data == "chat:profile")
async def view_partner_profile(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay una conversación activa.", show_alert=True)
        return

    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        viewer = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        if not viewer or not partner:
            await callback.answer("Perfil no disponible.", show_alert=True)
            return

        reveal_mutual = await profile_reveal_is_mutual(
            session,
            conversation_id,
        )

        await callback.answer()
        await send_profile_card(
            callback.bot,
            callback.from_user.id,
            partner,
            viewer=viewer,
            reply_markup=active_chat_keyboard(),
            force_full=reveal_mutual,
        )

@router.callback_query(F.data == "chat:like")
async def like_partner(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay conversación activa.", show_alert=True)
        return
    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        if not user or not partner:
            return
        _, mutual = await add_interest(
            session, user, partner, conversation_id, False
        )

    if mutual:
        await callback.answer("¡Interés mutuo! ❤️", show_alert=True)
        await callback.message.answer(
            "💘 <b>¡Hay interés mutuo!</b>\n\n"
            "Ambos indicaron que quieren conocerse mejor. "
            "Por ahora pueden seguir hablando anónimamente."
        )
        await callback.bot.send_message(
            partner_tg,
            "💘 <b>¡Hay interés mutuo!</b>\n\n"
            "Ambos indicaron que quieren conocerse mejor. "
            "Por ahora pueden seguir hablando anónimamente.",
        )
    else:
        await callback.answer("Interés guardado ❤️")


@router.callback_query(F.data == "chat:super")
async def super_interest(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay conversación activa.", show_alert=True)
        return
    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        if not user or not partner:
            return

        balance = await get_balance(session, user, "super_interest")
        if balance < 1:
            await callback.answer(
                "No tienes Super Intereses. Puedes obtener uno en 👑 Premium.",
                show_alert=True,
            )
            return

        if not await consume(session, user, "super_interest", 1):
            await callback.answer("No se pudo consumir el crédito.", show_alert=True)
            return

        _, mutual = await add_interest(
            session, user, partner, conversation_id, True
        )

    await callback.answer("Super Interés enviado 💘")
    await callback.bot.send_message(
        partner_tg,
        "💘 <b>La persona con la que hablas te envió un Super Interés.</b>",
        reply_markup=active_chat_keyboard(),
    )
    if mutual:
        await callback.message.answer("❤️ Además, el interés ya es mutuo.")


@router.message()
async def relay_active_chat(message: Message) -> None:
    # Evita que botones/comandos del propio bot se reenvíen accidentalmente.
    if message.text and (
        message.text.startswith("/")
        or message.text
        in {
            "🎲 Buscar persona",
            "📍 Personas cerca",
            "❤️ Likes recibidos",
            "👤 Mi perfil",
            "🌎 Explorar",
            "🎁 Recompensas",
            "👑 Premium",
            "⚙️ Preferencias",
            "🛡️ Seguridad",
            "🚨 Reportar",
            "🚫 Bloquear",
            "⭐ Guardar favorito",
            "📲 Compartir Telegram",
            "💘 Super Interés",
            "👀 Conocer más",
            "⬅️ Acciones principales",
            "➡️ Más opciones",
            "⭐ Favoritos",
            "🕘 Historial",
            "❌ Terminar",
            "🔄 Siguiente",
            "🎁 Regalo",
            "❤️ Me interesa",
            "👤 Mi conexión",
            "🧭 Panel de chat",
            "⏭ Omitir por ahora",
        }
    ):
        return

    active = await get_active_partner(message.from_user.id)
    if not active:
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        restriction = await get_active_restriction(session, user)
        if restriction:
            await message.answer(restriction_text(restriction))
            return

    allowed, ttl = await chat_message_allowed(message.from_user.id)
    if not allowed:
        await message.answer(
            f"🤖 <b>FreXo</b>\n\n"
            f"⚠️ Estás enviando mensajes demasiado rápido. "
            f"Espera {ttl} segundos antes de continuar."
        )
        return

    partner_tg, _conversation_id = active
    sent = await relay_message(message.bot, message, partner_tg)
    if not sent:
        await message.answer(
            "🤖 <b>FreXo</b>\n\nEse tipo de contenido todavía no puede enviarse de forma anónima."
        )
