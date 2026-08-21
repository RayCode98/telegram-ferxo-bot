from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AnalyticsEvent,
    Block,
    Conversation,
    ConversationFeedback,
    Interest,
    Order,
    PaymentRefund,
    Report,
    StarTransaction,
    User,
)
from app.redis_client import redis


MATCHMAKING_QUEUE_KEY = "matchmaking:queue"


@dataclass(slots=True)
class DailyReport:
    generated_local: datetime
    start_utc: datetime
    end_utc: datetime

    new_users: int
    active_users_today: int
    active_users_15m: int

    searches: int
    searching_now: int
    matches: int
    active_conversations: int
    messages: int
    likes: int

    blocks: int
    reports: int

    feedback_good: int
    feedback_neutral: int
    feedback_bad: int

    purchases: int
    payers: int
    premium_purchases: int
    premium_active: int
    stars_gross: int
    stars_refunded: int

    @property
    def stars_net(self) -> int:
        return max(0, int(self.stars_gross) - int(self.stars_refunded))

    @property
    def purchase_conversion(self) -> float:
        if self.active_users_today <= 0:
            return 0.0
        return (self.payers / self.active_users_today) * 100.0


def _report_timezone():
    try:
        return ZoneInfo(settings.admin_report_timezone)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _today_bounds() -> tuple[datetime, datetime, datetime]:
    tz = _report_timezone()
    now_local = datetime.now(tz)
    start_local = datetime.combine(
        now_local.date(),
        time.min,
        tzinfo=tz,
    )
    end_local = start_local + timedelta(days=1)
    return (
        now_local,
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


async def _count_between(
    session: AsyncSession,
    model,
    column,
    start_utc: datetime,
    end_utc: datetime,
) -> int:
    value = (
        await session.execute(
            select(func.count(model.id)).where(
                column >= start_utc,
                column < end_utc,
            )
        )
    ).scalar_one()
    return int(value or 0)


async def build_daily_report(
    session: AsyncSession,
) -> DailyReport:
    now_local, start_utc, end_utc = _today_bounds()
    now_utc = datetime.now(timezone.utc)

    new_users = await _count_between(
        session,
        User,
        User.created_at,
        start_utc,
        end_utc,
    )

    active_users_today = int(
        (
            await session.execute(
                select(func.count(User.id)).where(
                    User.last_seen_at >= start_utc,
                    User.last_seen_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    active_users_15m = int(
        (
            await session.execute(
                select(func.count(User.id)).where(
                    User.last_seen_at >= now_utc - timedelta(minutes=15)
                )
            )
        ).scalar_one()
        or 0
    )

    searches = int(
        (
            await session.execute(
                select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.event_name == "search_started",
                    AnalyticsEvent.created_at >= start_utc,
                    AnalyticsEvent.created_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    matches = await _count_between(
        session,
        Conversation,
        Conversation.started_at,
        start_utc,
        end_utc,
    )

    active_conversations = int(
        (
            await session.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.status == "active"
                )
            )
        ).scalar_one()
        or 0
    )

    messages = int(
        (
            await session.execute(
                select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.event_name == "chat_message_relayed",
                    AnalyticsEvent.created_at >= start_utc,
                    AnalyticsEvent.created_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    likes = await _count_between(
        session,
        Interest,
        Interest.created_at,
        start_utc,
        end_utc,
    )

    blocks = await _count_between(
        session,
        Block,
        Block.created_at,
        start_utc,
        end_utc,
    )

    reports = await _count_between(
        session,
        Report,
        Report.created_at,
        start_utc,
        end_utc,
    )

    feedback_rows = await session.execute(
        select(
            ConversationFeedback.rating,
            func.count(ConversationFeedback.id),
        )
        .where(
            ConversationFeedback.created_at >= start_utc,
            ConversationFeedback.created_at < end_utc,
        )
        .group_by(ConversationFeedback.rating)
    )
    feedback = {
        str(rating): int(count)
        for rating, count in feedback_rows.all()
    }

    purchases = await _count_between(
        session,
        StarTransaction,
        StarTransaction.created_at,
        start_utc,
        end_utc,
    )

    payers = int(
        (
            await session.execute(
                select(
                    func.count(func.distinct(StarTransaction.user_id))
                ).where(
                    StarTransaction.created_at >= start_utc,
                    StarTransaction.created_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    premium_purchases = int(
        (
            await session.execute(
                select(func.count(StarTransaction.id))
                .join(
                    Order,
                    Order.id == StarTransaction.order_id,
                )
                .where(
                    StarTransaction.created_at >= start_utc,
                    StarTransaction.created_at < end_utc,
                    Order.product_code == "premium_monthly",
                )
            )
        ).scalar_one()
        or 0
    )

    premium_active = int(
        (
            await session.execute(
                select(func.count(User.id)).where(
                    User.premium_until > now_utc
                )
            )
        ).scalar_one()
        or 0
    )

    stars_gross = int(
        (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(StarTransaction.stars_amount),
                        0,
                    )
                ).where(
                    StarTransaction.created_at >= start_utc,
                    StarTransaction.created_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    stars_refunded = int(
        (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(PaymentRefund.stars_amount),
                        0,
                    )
                ).where(
                    PaymentRefund.refunded_at >= start_utc,
                    PaymentRefund.refunded_at < end_utc,
                )
            )
        ).scalar_one()
        or 0
    )

    try:
        searching_now = int(
            await redis.zcard(MATCHMAKING_QUEUE_KEY)
        )
    except Exception:
        searching_now = 0

    return DailyReport(
        generated_local=now_local,
        start_utc=start_utc,
        end_utc=end_utc,
        new_users=new_users,
        active_users_today=active_users_today,
        active_users_15m=active_users_15m,
        searches=searches,
        searching_now=searching_now,
        matches=matches,
        active_conversations=active_conversations,
        messages=messages,
        likes=likes,
        blocks=blocks,
        reports=reports,
        feedback_good=feedback.get("good", 0),
        feedback_neutral=feedback.get("neutral", 0),
        feedback_bad=feedback.get("bad", 0),
        purchases=purchases,
        payers=payers,
        premium_purchases=premium_purchases,
        premium_active=premium_active,
        stars_gross=stars_gross,
        stars_refunded=stars_refunded,
    )


def render_daily_report(report: DailyReport) -> str:
    date_label = report.generated_local.strftime("%d/%m/%Y")
    time_label = report.generated_local.strftime("%H:%M")

    return (
        f"📅 <b>HOY EN FREXO · {date_label}</b>\n"
        f"<i>Actualizado {time_label}</i>\n\n"

        "<b>👥 Usuarios</b>\n"
        f"🆕 Nuevos: <b>{report.new_users}</b>\n"
        f"☀️ Activos hoy: <b>{report.active_users_today}</b>\n"
        f"🟢 Activos últimos 15 min: <b>{report.active_users_15m}</b>\n\n"

        "<b>💬 Actividad</b>\n"
        f"🔎 Búsquedas iniciadas: <b>{report.searches}</b>\n"
        f"⏳ Buscando ahora: <b>{report.searching_now}</b>\n"
        f"🤝 Matches: <b>{report.matches}</b>\n"
        f"💬 Mensajes enviados: <b>{report.messages}</b>\n"
        f"🗨 Conversaciones activas: <b>{report.active_conversations}</b>\n"
        f"❤️ Likes / intereses: <b>{report.likes}</b>\n\n"

        "<b>⭐ Calidad y seguridad</b>\n"
        f"👍 Buena: <b>{report.feedback_good}</b> · "
        f"😐 Normal: <b>{report.feedback_neutral}</b> · "
        f"👎 Mala: <b>{report.feedback_bad}</b>\n"
        f"🚫 Bloqueos: <b>{report.blocks}</b>\n"
        f"🚨 Reportes: <b>{report.reports}</b>\n\n"

        "<b>💰 Monetización</b>\n"
        f"💳 Compras: <b>{report.purchases}</b>\n"
        f"👤 Compradores: <b>{report.payers}</b>\n"
        f"📈 Activo → comprador: <b>{report.purchase_conversion:.2f}%</b>\n"
        f"👑 Premium vendidos hoy: <b>{report.premium_purchases}</b>\n"
        f"👑 Premium activos totales: <b>{report.premium_active}</b>\n"
        f"⭐ Stars brutas: <b>{report.stars_gross}</b>\n"
        f"↩️ Reembolsos: <b>{report.stars_refunded}</b>\n"
        f"💎 Stars netas: <b>{report.stars_net}</b>"
    )
