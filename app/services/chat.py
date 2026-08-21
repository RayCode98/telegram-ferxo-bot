from __future__ import annotations

from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.config import settings


ALLOWED_CONTENT_TYPES = {
    "text",
    "photo",
    "video",
    "voice",
    "video_note",
    "animation",
    "sticker",
    "document",
    "audio",
}

USER_HEADER = "👤 <b>Tu conexión</b>"
SYSTEM_HEADER = "🤖 <b>FreXo</b>"

CONTENT_LABELS = {
    "photo": "envió una foto 📸",
    "video": "envió un video 🎬",
    "voice": "envió una nota de voz 🎙️",
    "video_note": "envió un video mensaje 🎥",
    "animation": "envió un GIF 🎞️",
    "sticker": "envió un sticker 🙂",
    "document": "envió un archivo 📎",
    "audio": "envió un audio 🎵",
}


def system_message(text: str) -> str:
    return f"{SYSTEM_HEADER}\n\n{text}"


async def _send_header_for_content(
    bot: Bot,
    partner_telegram_id: int,
    content_type: str,
) -> None:
    label = CONTENT_LABELS.get(content_type, "envió un contenido")
    await bot.send_message(
        partner_telegram_id,
        f"{USER_HEADER}\n<i>{label}</i>",
        protect_content=settings.protect_relayed_content,
    )


async def relay_message(
    bot: Bot,
    message: Message,
    partner_telegram_id: int,
) -> bool:
    """
    Todos los mensajes de la pareja quedan identificados con 👤 Tu conexión.
    Los textos se reconstruyen con HTML para conservar negritas, enlaces,
    emojis/entidades compatibles, etc. Los medios con caption reciben el
    mismo encabezado dentro del caption. Para stickers/video notes y otros
    contenidos sin caption, se envía una cabecera inmediatamente antes.
    """
    if message.content_type not in ALLOWED_CONTENT_TYPES:
        return False

    try:
        if message.content_type == "text" and message.text is not None:
            body = message.html_text
            formatted = f"{USER_HEADER}\n\n{body}"

            # Telegram admite hasta 4096 caracteres en texto.
            # Si el contenido queda demasiado cerca del límite, preservamos
            # el original usando copyMessage y enviamos la etiqueta aparte.
            if len(formatted) <= 4000:
                await bot.send_message(
                    chat_id=partner_telegram_id,
                    text=formatted,
                    protect_content=settings.protect_relayed_content,
                )
            else:
                await bot.send_message(
                    chat_id=partner_telegram_id,
                    text=USER_HEADER,
                    protect_content=settings.protect_relayed_content,
                )
                await message.copy_to(
                    chat_id=partner_telegram_id,
                    reply_markup=None,
                    protect_content=settings.protect_relayed_content,
                )
            return True

        if message.caption:
            caption_body = message.html_text
            formatted_caption = f"{USER_HEADER}\n\n{caption_body}"

            # caption admite 1024 caracteres; reservamos margen para entidades.
            if len(formatted_caption) <= 950:
                await message.copy_to(
                    chat_id=partner_telegram_id,
                    caption=formatted_caption,
                    parse_mode="HTML",
                    reply_markup=None,
                    protect_content=settings.protect_relayed_content,
                )
            else:
                await _send_header_for_content(
                    bot,
                    partner_telegram_id,
                    message.content_type,
                )
                await message.copy_to(
                    chat_id=partner_telegram_id,
                    reply_markup=None,
                    protect_content=settings.protect_relayed_content,
                )
            return True

        await _send_header_for_content(
            bot,
            partner_telegram_id,
            message.content_type,
        )
        await message.copy_to(
            chat_id=partner_telegram_id,
            reply_markup=None,
            protect_content=settings.protect_relayed_content,
        )
        return True

    except TelegramBadRequest:
        # Algunas entidades especiales pueden no ser reconstruibles por el bot.
        # En ese caso no perdemos el mensaje: mostramos la etiqueta anónima
        # y copiamos el contenido original sin información de reenvío.
        try:
            await bot.send_message(
                chat_id=partner_telegram_id,
                text=USER_HEADER,
                protect_content=settings.protect_relayed_content,
            )
            await message.copy_to(
                chat_id=partner_telegram_id,
                reply_markup=None,
                protect_content=settings.protect_relayed_content,
            )
            return True
        except TelegramBadRequest:
            return False
