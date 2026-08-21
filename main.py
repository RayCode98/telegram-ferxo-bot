import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.database import init_db
from app.health import mark_ready, run_health_server
from app.logging_config import configure_logging
from app.middlewares import ActivityMiddleware
from app.redis_client import close_redis
from app.services.quality import conversation_quality_monitor
from app.services.recovery import recover_runtime_state
from app.handlers import (
    personal_stats_router,
    weekly_router,
    feedback_router,
    admin_router,
    start_router,
    navigation_router,
    chat_actions_router,
    profile_router,
    interests_router,
    growth_router,
    gifts_router,
    matchmaking_router,
    notifications_router,
    history_router,
    payments_router,
    moderation_router,
    social_router,
    support_router,
    chat_router,
)

async def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    await init_db()
    recovery_summary = await recover_runtime_state()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    activity = ActivityMiddleware()
    dp.message.outer_middleware(activity)
    dp.callback_query.outer_middleware(activity)
    dp.pre_checkout_query.outer_middleware(activity)

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
    dp.include_router(feedback_router)
    dp.include_router(weekly_router)
    dp.include_router(personal_stats_router)
    dp.include_router(support_router)
    dp.include_router(chat_router)

    quality_task = asyncio.create_task(conversation_quality_monitor(bot))
    health_task = asyncio.create_task(run_health_server())
    mark_ready(recovery_summary)
    logger.info("frexo_ready", extra={"environment": settings.environment, **recovery_summary})

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), tasks_concurrency_limit=500)
    finally:
        for task in (quality_task, health_task): task.cancel()
        for task in (quality_task, health_task):
            try: await task
            except asyncio.CancelledError: pass
        await bot.session.close()
        await close_redis()

if __name__ == "__main__":
    asyncio.run(main())
