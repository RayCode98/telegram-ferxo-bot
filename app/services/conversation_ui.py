from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import active_chat_keyboard, chat_reply_keyboard, main_menu
from app.models import User
from app.redis_client import redis
from app.repositories import profile_reveal_is_mutual
from app.services.matchmaking import age_of
from app.services.profile import (
    approximate_distance_text,
    gender_label,
    premium_active,
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
    ]

    if full:
        lines.append(
            f"📍 {approximate_distance_text(viewer, partner)}"
        )
        if partner.bio:
            bio = partner.bio
            if len(bio) > 120:
                bio = bio[:117] + "…"
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
            "💬 Los mensajes marcados con <b>👤 Tu conexión</b> vienen de esta persona.",
            "🤖 Los avisos marcados con <b>FreXo</b> vienen del bot.",
            "",
            "📌 Este panel queda fijado arriba mientras la conversación esté activa.",
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

    # Si el panel pertenece a otra conversación, lo cerramos primero.
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
            # "message is not modified" significa que el panel ya está
            # actualizado; no debemos crear un segundo panel.
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

            # Si el mensaje fue eliminado manualmente o ya no puede editarse,
            # entonces sí generamos un panel nuevo.
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
        # Si un cliente/estado concreto impide pin, el panel sigue accesible
        # desde el teclado persistente.
        pass

    pipe = redis.pipeline()
    pipe.set(message_key, str(panel.message_id))
    pipe.set(conversation_key, conversation_id)
    await pipe.execute()

    # Instala el teclado inferior persistente.
    await bot.send_message(
        chat_id=viewer.telegram_id,
        text="🤖 <b>FreXo</b>\n\n"
             "Los controles de esta conversación permanecerán disponibles abajo.",
        reply_markup=chat_reply_keyboard(),
        protect_content=True,
    )

    return panel.message_id


async def close_chat_panel(
    bot: Bot,
    telegram_id: int,
    *,
    reason: str = "Conversación finalizada.",
) -> None:
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

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text="🏠 Menú principal",
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
    await ensure_chat_panel(bot, session, user, partner, conversation_id)
    await ensure_chat_panel(bot, session, partner, user, conversation_id)
