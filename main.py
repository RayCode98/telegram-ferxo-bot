import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.database import init_db
from app.middlewares import ActivityMiddleware
from app.redis_client import close_redis
from app.handlers import (
    admin_router, start_router, navigation_router, chat_actions_router,
    profile_router, interests_router, growth_router, gifts_router,
    matchmaking_router, notifications_router, history_router, payments_router,
    moderation_router, social_router, chat_router,
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

    activity_middleware = ActivityMiddleware()
    dp.message.outer_middleware(activity_middleware)
    dp.callback_query.outer_middleware(activity_middleware)
    dp.pre_checkout_query.outer_middleware(activity_middleware)

    # El orden importa: acciones específicas primero y relay genérico al final.
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(navigation_router)
    dp.include_router(chat_actions_router)
    dp.include_router(profile_router)
    dp.include_router(interests_router)
    dp.include_router(growth_router)
    dp.include_router(gifts_router)
    dp.include_router(matchmaking_router)
    dp.include_router(notifications_router)
    dp.include_router(history_router)
    dp.include_router(payments_router)
    dp.include_router(moderation_router)
    dp.include_router(social_router)
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
