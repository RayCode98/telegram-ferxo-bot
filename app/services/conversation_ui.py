from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import (
    active_chat_keyboard,
    chat_reply_keyboard,
    conversation_feedback_keyboard,
    main_menu,
)
from app.models import User
from app.redis_client import redis
from app.repositories import profile_reveal_is_mutual
from app.services.compatibility import compatibility_text
from app.services.matchmaking import age_of
from app.services.profile import (
    approximate_distance_text,
    gender_label,
    premium_active,
)
from app.services.social_graph import (
    activity_label,
    common_interests,
    interest_labels,
)


PANEL_MESSAGE_KEY = "chat:panel_message:{}"
PANEL_CONVERSATION_KEY = "chat:panel_conversation:{}"


async def panel_text(
    session: AsyncSession,
    viewer: User,
    partner: User,
    conversation_id: str,
) -> str:
    mutual_reveal = await profile_reveal_is_mutual(
        session,
        conversation_id,
    )
    full = premium_active(viewer) or mutual_reveal
    age = age_of(partner.birth_date) or "?"

    lines = [
        "🧭 <b>CONVERSACIÓN ACTIVA</b>",
        "",
        f"👤 <b>{partner.alias or 'Sin alias'}</b>",
        f"🎂 {age} años",
        f"🚻 {gender_label(partner.gender)}",
        await activity_label(session, partner),
        await compatibility_text(session, viewer, partner),
    ]

    common = await common_interests(session, viewer, partner)
    if common:
        labels = interest_labels(common)
        lines.append("💬 Rompehielo: pregúntale por " + labels[0])

    if full:
        lines.append(f"📍 {approximate_distance_text(viewer, partner)}")
        if partner.bio:
            bio = partner.bio if len(partner.bio) <= 120 else partner.bio[:117] + "…"
            lines.extend(["", f"📝 {bio}"])
    else:
        lines.extend(
            [
                "",
                "🔒 Foto, bio y distancia: perfil ampliado.",
                "👀 Usa «Conocer más» para desbloquearlo por consentimiento mutuo.",
            ]
        )

    lines.extend(
        [
            "",
            "────────────────",
            "👤 Tu conexión = mensajes de la persona.",
            "🤖 FreXo = avisos del sistema.",
            "",
            "📌 Panel fijado mientras dure la conversación.",
            "⌨️ Usa «➡️ Más opciones» para ver seguridad y funciones sociales.",
        ]
    )
    return "\n".join(lines)


async def ensure_chat_panel(
    bot: Bot,
    session: AsyncSession,
    viewer: User,
    partner: User,
    conversation_id: str,
) -> int:
    message_key = PANEL_MESSAGE_KEY.format(viewer.telegram_id)
    conversation_key = PANEL_CONVERSATION_KEY.format(viewer.telegram_id)

    old_message_id = await redis.get(message_key)
    old_conversation_id = await redis.get(conversation_key)

    if old_message_id and old_conversation_id != conversation_id:
        try:
            await bot.unpin_chat_message(
                chat_id=viewer.telegram_id,
                message_id=int(old_message_id),
            )
        except TelegramBadRequest:
            pass
        old_message_id = None

    text = await panel_text(
        session,
        viewer,
        partner,
        conversation_id,
    )

    if old_message_id:
        try:
            await bot.edit_message_text(
                chat_id=viewer.telegram_id,
                message_id=int(old_message_id),
                text=text,
                reply_markup=active_chat_keyboard(),
            )
            await redis.set(conversation_key, conversation_id)
            return int(old_message_id)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                try:
                    await bot.pin_chat_message(
                        chat_id=viewer.telegram_id,
                        message_id=int(old_message_id),
                        disable_notification=True,
                    )
                except TelegramBadRequest:
                    pass

                await redis.set(conversation_key, conversation_id)
                return int(old_message_id)

            old_message_id = None

    panel = await bot.send_message(
        chat_id=viewer.telegram_id,
        text=text,
        reply_markup=active_chat_keyboard(),
        protect_content=True,
    )

    try:
        await bot.pin_chat_message(
            chat_id=viewer.telegram_id,
            message_id=panel.message_id,
            disable_notification=True,
        )
    except TelegramBadRequest:
        pass

    pipe = redis.pipeline()
    pipe.set(message_key, str(panel.message_id))
    pipe.set(conversation_key, conversation_id)
    await pipe.execute()

    await bot.send_message(
        chat_id=viewer.telegram_id,
        text=(
            "🤖 <b>FreXo</b>\n\n"
            "Acciones principales disponibles abajo. "
            "Pulsa «➡️ Más opciones» para ver el resto."
        ),
        reply_markup=chat_reply_keyboard(page=1),
        protect_content=True,
    )

    return panel.message_id


async def set_chat_keyboard_page(
    bot: Bot,
    telegram_id: int,
    page: int,
) -> None:
    await bot.send_message(
        chat_id=telegram_id,
        text=(
            "🤖 <b>FreXo</b>\n\n"
            + (
                "Mostrando acciones adicionales."
                if page == 2
                else "Mostrando acciones principales."
            )
        ),
        reply_markup=chat_reply_keyboard(page=page),
        protect_content=True,
    )


async def close_chat_panel(
    bot: Bot,
    telegram_id: int,
    *,
    reason: str = "Conversación finalizada.",
    notice: str | None = None,
    conversation_id: str | None = None,
    ask_feedback: bool = False,
) -> None:
    """
    Cierra el panel y muestra el motivo antes de devolver el menú principal.
    Esto evita que el usuario sólo vea "Menú principal" sin entender qué pasó.
    """
    message_key = PANEL_MESSAGE_KEY.format(telegram_id)
    conversation_key = PANEL_CONVERSATION_KEY.format(telegram_id)
    message_id = await redis.get(message_key)

    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=telegram_id,
                message_id=int(message_id),
                text=(
                    "🤖 <b>FreXo</b>\n\n"
                    f"✅ {reason}\n\n"
                    "Este panel ya no corresponde a una conversación activa."
                ),
            )
        except TelegramBadRequest:
            pass

        try:
            await bot.unpin_chat_message(
                chat_id=telegram_id,
                message_id=int(message_id),
            )
        except TelegramBadRequest:
            pass

    await redis.delete(message_key, conversation_key)

    if notice:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="🤖 <b>FreXo</b>\n\n" + notice,
            )
        except TelegramBadRequest:
            pass

    if ask_feedback and conversation_id:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    "⭐ <b>¿Cómo estuvo esta conversación?</b>\n\n"
                    "Tu valoración ayuda a mejorar FreXo. "
                    "Una opinión negativa por sí sola no genera sanciones."
                ),
                reply_markup=conversation_feedback_keyboard(conversation_id),
            )
        except TelegramBadRequest:
            pass

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text="🏠 <b>Menú principal</b>",
            reply_markup=main_menu(),
        )
    except TelegramBadRequest:
        pass


async def refresh_pair_panels(
    bot: Bot,
    session: AsyncSession,
    user: User,
    partner: User,
    conversation_id: str,
) -> None:
    await ensure_chat_panel(
        bot,
        session,
        user,
        partner,
        conversation_id,
    )
    await ensure_chat_panel(
        bot,
        session,
        partner,
        user,
        conversation_id,
    )
