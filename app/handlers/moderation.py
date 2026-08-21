from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.keyboards import report_keyboard
from app.repositories import (
    add_block,
    add_report,
    end_conversation,
    get_user_by_telegram,
)
from app.services.security import report_allowed
from app.services.conversation_ui import close_chat_panel
from app.services.matchmaking import (
    clear_active_pair,
    get_active_partner,
)


router = Router(name="moderation")


@router.callback_query(F.data == "chat:report")
async def choose_report_reason(callback: CallbackQuery) -> None:
    if not await get_active_partner(callback.from_user.id):
        await callback.answer("No hay una conversación activa.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "🚨 <b>¿Qué ocurrió?</b>",
        reply_markup=report_keyboard(),
    )


@router.callback_query(F.data.startswith("report:"))
async def submit_report(callback: CallbackQuery) -> None:
    allowed, ttl = await report_allowed(callback.from_user.id)
    if not allowed:
        await callback.answer(
            "Alcanzaste el límite de reportes por hoy. Si existe un riesgo inmediato, "
            "termina y bloquea la conversación.",
            show_alert=True,
        )
        return

    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("La conversación ya terminó.", show_alert=True)
        return

    partner_tg, conversation_id = active
    reason = callback.data.split(":", 1)[1]

    async with SessionLocal() as session:
        reporter = await get_user_by_telegram(session, callback.from_user.id)
        reported = await get_user_by_telegram(session, partner_tg)
        if reporter and reported:
            await add_report(
                session,
                reporter,
                reported,
                conversation_id,
                reason,
            )
            await end_conversation(
                session,
                conversation_id,
                reporter.id,
                "reported",
            )

    await clear_active_pair(callback.from_user.id, partner_tg)
    await close_chat_panel(
        callback.bot,
        callback.from_user.id,
        reason="Conversación terminada tras tu reporte.",
        notice="🚨 Reporte enviado y conversación cerrada.",
        conversation_id=conversation_id,
        ask_feedback=False,
    )
    await close_chat_panel(
        callback.bot,
        partner_tg,
        reason="La conversación fue cerrada por seguridad.",
        notice=(
            "👋 <b>La conversación fue cerrada.</b>\n\n"
            "Ya puedes volver al menú principal."
        ),
        conversation_id=conversation_id,
        ask_feedback=False,
    )
    await callback.answer("Reporte enviado")
    await callback.message.edit_text(
        "✅ Reporte enviado y conversación terminada."
    )
    await callback.bot.send_message(
        partner_tg,
        "🤖 <b>FreXo</b>\n\nLa conversación terminó.",
    )


@router.callback_query(F.data == "chat:block")
async def block_partner(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay conversación activa.", show_alert=True)
        return

    partner_tg, conversation_id = active
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        if user and partner:
            await add_block(session, user, partner)
            await end_conversation(
                session,
                conversation_id,
                user.id,
                "blocked",
            )

    await clear_active_pair(callback.from_user.id, partner_tg)
    await close_chat_panel(
        callback.bot,
        callback.from_user.id,
        reason="Usuario bloqueado.",
        notice="🚫 Usuario bloqueado. No volverán a ser emparejados.",
        conversation_id=conversation_id,
        ask_feedback=False,
    )
    await close_chat_panel(
        callback.bot,
        partner_tg,
        reason="La conversación terminó.",
        notice="👋 <b>La conversación terminó.</b>",
        conversation_id=conversation_id,
        ask_feedback=False,
    )
    await callback.answer("Usuario bloqueado")
    await callback.message.edit_text(
        "🚫 Usuario bloqueado. No volverán a ser emparejados."
    )
    await callback.bot.send_message(
        partner_tg,
        "🤖 <b>FreXo</b>\n\nLa conversación terminó.",
    )
