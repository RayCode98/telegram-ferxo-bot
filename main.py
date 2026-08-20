import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.database import init_db
from app.redis_client import close_redis
from app.handlers import (
    start_router,
    profile_router,
    matchmaking_router,
    payments_router,
    moderation_router,
    chat_router,
)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # El orden importa: el relay genérico del chat debe quedar al final.
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(matchmaking_router)
    dp.include_router(payments_router)
    dp.include_router(moderation_router)
    dp.include_router(chat_router)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
