from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


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


async def relay_message(
    bot: Bot,
    message: Message,
    partner_telegram_id: int,
) -> bool:
    # copy_to usa copyMessage: no muestra "reenviado de" ni revela
    # automáticamente la cuenta Telegram del remitente.
    if message.content_type not in ALLOWED_CONTENT_TYPES:
        return False

    try:
        await message.copy_to(
            chat_id=partner_telegram_id,
            reply_markup=None,
        )
        return True
    except TelegramBadRequest:
        return False
