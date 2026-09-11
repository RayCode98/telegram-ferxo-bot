from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import and_, func, or_, select

from app.config import settings
from app.database import SessionLocal
from app.keyboards import (
    active_chat_reminder_keyboard,
    onboarding_reminder_keyboard,
    profile_reminder_keyboard,
    premium_offer_keyboard,
)
from app.models import (
    AccountLifecycle,
    Conversation,
    ConversationQuality,
    AnalyticsEvent,
    Order,
    StarTransaction,
    User,
    UserInterest,
)
from app.redis_client import redis
from app.repositories import get_user_by_id
from app.services.matchmaking import get_active_partner
from app.services.analytics import track_event
from app.services.monetization import record_paywall_view, render_premium_offer


PROFILE_ACTIVE_WINDOW_DAYS = 30
ONBOARDING_ACTIVE_WINDOW_DAYS = 14


def _hours_ttl(hours: int) -> int:
    return max(3600, int(hours) * 3600)


async def _profile_missing_items(session, user: User) -> list[str]:
    missing: list[str] = []

    if not user.photo_file_id:
        missing.append("📸 una foto")
    if not (user.bio or "").strip():
        missing.append("📝 una bio")

    interest_count = int(
        (
            await session.execute(
                select(func.count(UserInterest.id)).where(
                    UserInterest.user_id == user.id
                )
            )
        ).scalar_one()
        or 0
    )
    if interest_count < 3:
        missing.append("🎯 al menos 3 intereses")

    return missing


async def send_profile_completion_reminders(bot: Bot) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=PROFILE_ACTIVE_WINDOW_DAYS)
    sent = 0

    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .outerjoin(
                AccountLifecycle,
                AccountLifecycle.user_id == User.id,
            )
            .where(
                User.onboarding_completed.is_(True),
                User.is_banned.is_(False),
                User.last_seen_at >= cutoff,
                or_(
                    AccountLifecycle.state.is_(None),
                    AccountLifecycle.state == "active",
                ),
            )
            .order_by(User.last_seen_at.desc())
            .limit(250)
        )

        for user in result.scalars():
            # No interrumpimos a alguien que ya está conversando.
            if await get_active_partner(user.telegram_id):
                continue

            key = f"reminder:profile:{user.telegram_id}"
            if await redis.exists(key):
                continue

            missing = await _profile_missing_items(session, user)
            if not missing:
                continue

            completed = 3 - len(missing)
            percent = int((completed / 3) * 100)
            items = "\n".join(f"• {item}" for item in missing)

            try:
                await bot.send_message(
                    user.telegram_id,
                    "👤 <b>Tu perfil FreXo todavía puede mejorar</b>\n\n"
                    f"Progreso aproximado: <b>{percent}%</b>\n\n"
                    "Te falta:\n"
                    f"{items}\n\n"
                    "Un perfil más completo ayuda a que tu conexión tenga más contexto "
                    "y permite calcular mejor los intereses en común.",
                    reply_markup=profile_reminder_keyboard(),
                )
            except Exception:
                continue

            await redis.set(
                key,
                "1",
                ex=_hours_ttl(settings.profile_reminder_hours),
            )
            sent += 1

    return sent


async def send_onboarding_reminders(bot: Bot) -> int:
    now = datetime.now(timezone.utc)
    min_age = now - timedelta(hours=settings.onboarding_reminder_delay_hours)
    active_cutoff = now - timedelta(days=ONBOARDING_ACTIVE_WINDOW_DAYS)
    sent = 0

    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .outerjoin(
                AccountLifecycle,
                AccountLifecycle.user_id == User.id,
            )
            .where(
                User.onboarding_completed.is_(False),
                User.is_banned.is_(False),
                User.created_at <= min_age,
                User.last_seen_at >= active_cutoff,
                or_(
                    AccountLifecycle.state.is_(None),
                    AccountLifecycle.state == "active",
                ),
            )
            .order_by(User.last_seen_at.desc())
            .limit(200)
        )

        for user in result.scalars():
            key = f"reminder:onboarding:{user.telegram_id}"
            if await redis.exists(key):
                continue

            try:
                await bot.send_message(
                    user.telegram_id,
                    "👋 <b>Aún no terminaste tu perfil de FreXo</b>\n\n"
                    "Completar el registro toma muy poco y es necesario para que podamos "
                    "encontrarte conexiones compatibles.\n\n"
                    "▶️ Continúa desde donde lo dejaste.",
                    reply_markup=onboarding_reminder_keyboard(),
                )
            except Exception:
                continue

            await redis.set(
                key,
                "1",
                ex=_hours_ttl(settings.onboarding_reminder_hours),
            )
            sent += 1

    return sent


async def send_active_chat_start_reminders(bot: Bot) -> int:
    """
    Recuerda una sola vez por conversación a cada integrante que todavía no ha
    enviado ningún mensaje después de varios minutos del match.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=settings.active_chat_reminder_minutes)
    sent = 0

    async with SessionLocal() as session:
        result = await session.execute(
            select(Conversation, ConversationQuality)
            .outerjoin(
                ConversationQuality,
                ConversationQuality.conversation_id == Conversation.id,
            )
            .where(
                Conversation.status == "active",
                Conversation.started_at <= cutoff,
            )
            .order_by(Conversation.started_at.desc())
            .limit(200)
        )

        for conversation, quality in result.all():
            user1 = await get_user_by_id(session, conversation.user1_id)
            user2 = await get_user_by_id(session, conversation.user2_id)
            if not user1 or not user2:
                continue

            counts = {
                user1.id: quality.user1_messages if quality else 0,
                user2.id: quality.user2_messages if quality else 0,
            }

            for user, partner in ((user1, user2), (user2, user1)):
                if counts[user.id] > 0:
                    continue

                key = f"reminder:active_chat:{conversation.id}:{user.id}"
                if await redis.exists(key):
                    continue

                partner_has_written = counts[partner.id] > 0
                if partner_has_written:
                    headline = "💬 <b>Tu conexión ya te escribió</b>"
                    detail = (
                        f"<b>{partner.alias or 'Tu conexión'}</b> está esperando tu respuesta."
                    )
                else:
                    headline = "💬 <b>Tienes una conversación activa</b>"
                    detail = (
                        f"Ya hiciste match con <b>{partner.alias or 'una conexión'}</b>, "
                        "pero todavía no has enviado tu primer mensaje."
                    )

                try:
                    await bot.send_message(
                        user.telegram_id,
                        f"🤖 <b>FreXo</b>\n\n{headline}\n\n"
                        f"{detail}\n\n"
                        "✍️ <b>Escribe directamente en este chat para comenzar.</b>\n"
                        "No necesitas pulsar ningún botón antes de mandar mensaje.",
                        reply_markup=active_chat_reminder_keyboard(),
                    )
                except Exception:
                    continue

                # Sólo una vez por usuario y conversación. La conversación se
                # cerrará por inactividad si finalmente nadie participa.
                await redis.set(
                    key,
                    "1",
                    ex=max(
                        3600,
                        settings.conversation_idle_close_hours * 3600 + 3600,
                    ),
                )
                sent += 1

    return sent


async def send_premium_preview_expiry_reminders(bot: Bot) -> int:
    """Offer paid Premium once after the one-time Preview has expired."""
    now = datetime.now(timezone.utc)
    sent = 0

    async with SessionLocal() as session:
        granted_users = select(AnalyticsEvent.user_id).where(
            AnalyticsEvent.event_name == "premium_preview_granted",
            AnalyticsEvent.user_id.is_not(None),
        )
        expired_users = select(AnalyticsEvent.user_id).where(
            AnalyticsEvent.event_name == "premium_preview_expired",
            AnalyticsEvent.user_id.is_not(None),
        )
        paid_premium_users = (
            select(StarTransaction.user_id)
            .join(Order, Order.id == StarTransaction.order_id)
            .where(Order.product_code.in_({"premium_monthly", "frexo_pass_7d"}))
        )

        result = await session.execute(
            select(User).where(
                User.id.in_(granted_users),
                User.id.not_in(expired_users),
                User.id.not_in(paid_premium_users),
                User.is_banned.is_(False),
                User.premium_until.is_not(None),
                User.premium_until <= now,
            ).limit(150)
        )

        for user in result.scalars():
            # Do not interrupt an active conversation; try again later.
            if await get_active_partner(user.telegram_id):
                continue

            try:
                await record_paywall_view(session, user, "preview_expired")
                await track_event(
                    session,
                    user,
                    "premium_preview_expired",
                    {"expired_at": user.premium_until.isoformat() if user.premium_until else None},
                )
                await bot.send_message(
                    user.telegram_id,
                    render_premium_offer("preview_expired"),
                    reply_markup=premium_offer_keyboard("preview_expired"),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                continue

            sent += 1

    return sent


async def reminder_monitor_iteration(bot: Bot) -> None:
    await send_onboarding_reminders(bot)
    await send_profile_completion_reminders(bot)
    await send_active_chat_start_reminders(bot)
    await send_premium_preview_expiry_reminders(bot)


async def user_reminder_monitor(bot: Bot) -> None:
    while True:
        try:
            await reminder_monitor_iteration(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Los recordatorios nunca deben detener el bot principal.
            pass

        await asyncio.sleep(max(300, settings.reminder_scan_interval_seconds))
