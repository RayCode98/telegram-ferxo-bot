from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AcquisitionCampaign,
    AnalyticsEvent,
    CampaignAttribution,
    Conversation,
    ConversationQuality,
    StarTransaction,
    User,
)


@dataclass(slots=True)
class FunnelStage:
    key: str
    label: str
    emoji: str
    count: int


@dataclass(slots=True)
class FunnelReport:
    days: int
    since: datetime
    until: datetime
    filter_kind: str
    filter_value: str | None
    filter_label: str
    stages: list[FunnelStage]
    d1_eligible: int
    d1_retained: int
    buyers: int
    stars: int

    @property
    def cohort_total(self) -> int:
        return self.stages[0].count if self.stages else 0

    @property
    def d1_rate(self) -> float:
        return (
            self.d1_retained / self.d1_eligible * 100.0
            if self.d1_eligible
            else 0.0
        )

    @property
    def buyer_rate(self) -> float:
        return (
            self.buyers / self.cohort_total * 100.0
            if self.cohort_total
            else 0.0
        )


@dataclass(slots=True)
class FunnelCampaignChoice:
    code: str
    name: str
    users: int
    active: bool


def _cohort_filters(
    since: datetime,
    until: datetime,
    *,
    filter_kind: str,
    filter_value: str | None,
):
    filters = [
        User.created_at >= since,
        User.created_at < until,
    ]

    if filter_kind == 'gender' and filter_value in {'male', 'female'}:
        filters.append(User.gender == filter_value)

    if filter_kind == 'campaign' and filter_value:
        filters.append(
            User.id.in_(
                select(CampaignAttribution.user_id)
                .join(
                    AcquisitionCampaign,
                    AcquisitionCampaign.id == CampaignAttribution.campaign_id,
                )
                .where(AcquisitionCampaign.code == filter_value)
            )
        )

    return filters


async def _filter_label(
    session: AsyncSession,
    filter_kind: str,
    filter_value: str | None,
) -> str:
    if filter_kind == 'gender':
        if filter_value == 'male':
            return '👨 Hombres'
        if filter_value == 'female':
            return '👩 Mujeres'

    if filter_kind == 'campaign' and filter_value:
        campaign = (
            await session.execute(
                select(AcquisitionCampaign).where(
                    AcquisitionCampaign.code == filter_value
                )
            )
        ).scalar_one_or_none()
        if campaign:
            return f'📣 {campaign.name}'
        return f'📣 {filter_value}'

    return '🌐 Todos los usuarios'


async def build_funnel_report(
    session: AsyncSession,
    *,
    days: int = 7,
    filter_kind: str = 'all',
    filter_value: str | None = None,
) -> FunnelReport:
    days = 30 if days == 30 else 7
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    filters = _cohort_filters(
        since,
        until,
        filter_kind=filter_kind,
        filter_value=filter_value,
    )
    cohort_ids = select(User.id).where(*filters)

    total = int(
        (
            await session.execute(
                select(func.count(User.id)).where(*filters)
            )
        ).scalar_one()
        or 0
    )

    completed = int(
        (
            await session.execute(
                select(func.count(User.id)).where(
                    *filters,
                    User.onboarding_completed.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    searched = int(
        (
            await session.execute(
                select(func.count(func.distinct(AnalyticsEvent.user_id))).where(
                    AnalyticsEvent.user_id.in_(cohort_ids),
                    AnalyticsEvent.event_name == 'search_started',
                    AnalyticsEvent.created_at >= since,
                    AnalyticsEvent.created_at < until,
                )
            )
        ).scalar_one()
        or 0
    )

    matched = int(
        (
            await session.execute(
                select(func.count(func.distinct(User.id)))
                .join(
                    Conversation,
                    or_(
                        Conversation.user1_id == User.id,
                        Conversation.user2_id == User.id,
                    ),
                )
                .where(
                    *filters,
                    Conversation.started_at >= since,
                    Conversation.started_at < until,
                )
            )
        ).scalar_one()
        or 0
    )

    first_message = int(
        (
            await session.execute(
                select(func.count(func.distinct(AnalyticsEvent.user_id))).where(
                    AnalyticsEvent.user_id.in_(cohort_ids),
                    AnalyticsEvent.event_name == 'chat_message_relayed',
                    AnalyticsEvent.created_at >= since,
                    AnalyticsEvent.created_at < until,
                )
            )
        ).scalar_one()
        or 0
    )

    replied_conversation = int(
        (
            await session.execute(
                select(func.count(func.distinct(User.id)))
                .join(
                    Conversation,
                    or_(
                        Conversation.user1_id == User.id,
                        Conversation.user2_id == User.id,
                    ),
                )
                .join(
                    ConversationQuality,
                    ConversationQuality.conversation_id == Conversation.id,
                )
                .where(
                    *filters,
                    Conversation.started_at >= since,
                    Conversation.started_at < until,
                    ConversationQuality.user1_messages > 0,
                    ConversationQuality.user2_messages > 0,
                )
            )
        ).scalar_one()
        or 0
    )

    buyer_row = await session.execute(
        select(
            func.count(func.distinct(StarTransaction.user_id)),
            func.coalesce(func.sum(StarTransaction.stars_amount), 0),
        ).where(
            StarTransaction.user_id.in_(cohort_ids),
            StarTransaction.created_at >= since,
            StarTransaction.created_at < until,
        )
    )
    buyers, stars = buyer_row.one()
    buyers = int(buyers or 0)
    stars = int(stars or 0)

    # D1 se calcula sólo con usuarios que ya tuvieron al menos 24 horas
    # para regresar. last_seen_at >= created_at + 24h se considera retorno.
    retention_rows = (
        await session.execute(
            select(User.created_at, User.last_seen_at).where(*filters)
        )
    ).all()
    mature_cutoff = until - timedelta(hours=24)
    d1_eligible = 0
    d1_retained = 0
    for created_at, last_seen_at in retention_rows:
        if created_at is None or created_at > mature_cutoff:
            continue
        d1_eligible += 1
        if last_seen_at and last_seen_at >= created_at + timedelta(hours=24):
            d1_retained += 1

    label = await _filter_label(session, filter_kind, filter_value)

    return FunnelReport(
        days=days,
        since=since,
        until=until,
        filter_kind=filter_kind,
        filter_value=filter_value,
        filter_label=label,
        stages=[
            FunnelStage('entered', 'Entraron al bot', '🚪', total),
            FunnelStage('completed', 'Completaron perfil', '✅', completed),
            FunnelStage('searched', 'Iniciaron búsqueda', '🔎', searched),
            FunnelStage('matched', 'Consiguieron match', '🤝', matched),
            FunnelStage('first_message', 'Mandaron primer mensaje', '✍️', first_message),
            FunnelStage('reply', 'Obtuvieron conversación real', '💬', replied_conversation),
        ],
        d1_eligible=d1_eligible,
        d1_retained=d1_retained,
        buyers=buyers,
        stars=stars,
    )


async def funnel_campaign_choices(
    session: AsyncSession,
    *,
    days: int = 7,
    limit: int = 10,
) -> list[FunnelCampaignChoice]:
    days = 30 if days == 30 else 7
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                AcquisitionCampaign.code,
                AcquisitionCampaign.name,
                AcquisitionCampaign.active,
                func.count(func.distinct(CampaignAttribution.user_id)).label('users'),
            )
            .join(
                CampaignAttribution,
                CampaignAttribution.campaign_id == AcquisitionCampaign.id,
            )
            .join(User, User.id == CampaignAttribution.user_id)
            .where(User.created_at >= since)
            .group_by(
                AcquisitionCampaign.id,
                AcquisitionCampaign.code,
                AcquisitionCampaign.name,
                AcquisitionCampaign.active,
            )
            .order_by(func.count(func.distinct(CampaignAttribution.user_id)).desc())
            .limit(limit)
        )
    ).all()

    return [
        FunnelCampaignChoice(
            code=code,
            name=name,
            users=int(users or 0),
            active=bool(active),
        )
        for code, name, active, users in rows
    ]


def render_funnel_report(report: FunnelReport) -> str:
    period = f'Últimos {report.days} días'
    start_label = report.since.strftime('%d/%m')
    end_label = report.until.strftime('%d/%m/%Y')

    lines = [
        f'📉 <b>Embudo FreXo · {period}</b>',
        f'<i>Cohorte {start_label} → {end_label}</i>',
        f'Filtro: <b>{report.filter_label}</b>',
        '',
        '<b>🎯 Conversión de nuevos usuarios</b>',
    ]

    previous = None
    rates: list[tuple[float, str]] = []
    for index, stage in enumerate(report.stages, start=1):
        if previous is None:
            lines.append(
                f'{index}. {stage.emoji} {stage.label}: <b>{stage.count}</b> · 100%'
            )
        else:
            rate = (stage.count / previous * 100.0) if previous else 0.0
            lines.append(
                f'{index}. {stage.emoji} {stage.label}: <b>{stage.count}</b> '
                f'· <b>{rate:.1f}%</b> del paso anterior'
            )
            rates.append((rate, f'{report.stages[index - 2].label} → {stage.label}'))
        previous = stage.count

    lines.extend([
        '',
        '<b>🔁 Retención</b>',
        f'👥 Elegibles para D1: <b>{report.d1_eligible}</b>',
        f'↩️ Regresaron después de 24 h: <b>{report.d1_retained}</b> '
        f'({report.d1_rate:.1f}%)',
        '',
        '<b>💰 Monetización de la cohorte</b>',
        f'👤 Compradores: <b>{report.buyers}</b> ({report.buyer_rate:.2f}%)',
        f'⭐ Stars generadas: <b>{report.stars}</b>',
    ])

    if rates:
        worst_rate, worst_name = min(rates, key=lambda item: item[0])
        lines.extend([
            '',
            '<b>⚠️ Mayor fuga del embudo</b>',
            f'{worst_name}: <b>{worst_rate:.1f}%</b> avanza al siguiente paso.',
        ])

    lines.extend([
        '',
        '<i>“Conversación real” = una conversación donde ambos usuarios enviaron '
        'al menos un mensaje. D1 sólo usa usuarios con 24 h o más desde su alta.</i>',
    ])
    return '\n'.join(lines)
