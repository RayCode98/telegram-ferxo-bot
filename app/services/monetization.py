from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AnalyticsEvent, Conversation, ConversationQuality, Order, StarTransaction, User
from app.services.analytics import track_event

PREMIUM_PRODUCTS = {"premium_monthly", "frexo_pass_7d"}

TRIGGER_LABELS = {
    "premium_menu": "Menú Premium",
    "likes_received": "Likes recibidos",
    "filter_age": "Filtro de edad",
    "filter_distance": "Filtro de distancia",
    "search_limit": "Límite de búsquedas",
    "preview_expired": "Fin de Premium Preview",
    "store": "Tienda",
    "other": "Otro",
}


def trigger_label(trigger: str) -> str:
    return TRIGGER_LABELS.get(trigger, trigger.replace("_", " ").title())


def render_premium_offer(trigger: str, *, likes_count: int = 0) -> str:
    if trigger == "likes_received" and likes_count > 0:
        intro = (
            f"❤️ <b>{likes_count} persona{'s' if likes_count != 1 else ''} "
            "mostraron interés en ti.</b>\n\n"
            "Descubre quiénes son y decide si quieres devolverles el interés."
        )
        benefits = (
            "• ❤️ Ver quién mostró interés en ti\n"
            "• 👤 Perfiles ampliados desde el inicio\n"
            "• 🎯 Filtros avanzados de edad y distancia\n"
            "• ⚡ Prioridad en tus búsquedas"
        )
    elif trigger == "filter_age":
        intro = (
            "🎂 <b>Encuentra personas dentro del rango de edad que prefieras.</b>\n\n"
            "El filtro preciso de edad forma parte de FreXo Premium."
        )
        benefits = (
            "• 🎂 Edad mínima y máxima personalizada\n"
            "• 📍 Radio de búsqueda preciso\n"
            "• 👤 Perfiles ampliados\n"
            "• ⚡ Prioridad en matchmaking"
        )
    elif trigger == "filter_distance":
        intro = (
            "📍 <b>Tú decides qué tan cerca quieres buscar.</b>\n\n"
            "Premium permite elegir radios precisos de 5, 10, 25, 50 o 100 km."
        )
        benefits = (
            "• 📍 Control preciso de distancia\n"
            "• 🎂 Filtros avanzados de edad\n"
            "• 👤 Perfiles ampliados\n"
            "• ⚡ Prioridad en búsquedas"
        )
    elif trigger == "search_limit":
        intro = (
            "🔎 <b>Ya utilizaste tus búsquedas gratuitas de hoy.</b>\n\n"
            "Con Premium puedes seguir buscando sin ese límite diario."
        )
        benefits = (
            "• 🔎 Búsquedas sin límite diario\n"
            "• 🎯 Filtros avanzados\n"
            "• 👤 Perfiles ampliados\n"
            "• ⚡ Prioridad en matchmaking"
        )
    elif trigger == "preview_expired":
        intro = (
            "👑 <b>Tu experiencia Premium de bienvenida terminó.</b>\n\n"
            "Si te gustaron los beneficios, puedes conservarlos con Premium mensual "
            "o elegir un Pass de 7 días."
        )
        benefits = (
            "• ❤️ Likes recibidos\n"
            "• 🎯 Filtros avanzados\n"
            "• 👤 Perfiles ampliados\n"
            "• ⚡ Prioridad en búsquedas"
        )
    else:
        intro = (
            "👑 <b>Mejora tu experiencia en FreXo.</b>\n\n"
            "Hablar con personas sigue siendo gratis. Premium te da más control "
            "sobre cómo y a quién encuentras."
        )
        benefits = (
            "• ❤️ Descubre quién mostró interés en ti\n"
            "• 🎯 Filtros avanzados de edad y distancia\n"
            "• 👤 Perfiles ampliados desde el inicio\n"
            "• ⚡ Prioridad en tus búsquedas"
        )

    return (
        f"{intro}\n\n"
        f"<b>Incluye:</b>\n{benefits}\n\n"
        "<b>Elige cómo probarlo:</b>\n"
        "👑 Premium · <b>199 ⭐ / 30 días</b>\n"
        "   Renovación automática; puedes cancelarla cuando quieras.\n\n"
        "✨ FreXo Pass · <b>69 ⭐ / 7 días</b>\n"
        "   Compra única; no se renueva automáticamente.\n\n"
        "🔐 El pago se realiza mediante Telegram Stars. FreXo no recibe tus datos bancarios."
    )


async def record_paywall_view(
    session: AsyncSession,
    user: User,
    trigger: str,
    *,
    likes_count: int | None = None,
) -> None:
    metadata = {"trigger": trigger}
    if likes_count is not None:
        metadata["likes_count"] = int(likes_count)
    await track_event(session, user, "premium_paywall_view", metadata)


async def record_paywall_click(
    session: AsyncSession,
    user: User,
    trigger: str,
    product_code: str,
) -> None:
    await track_event(
        session,
        user,
        "premium_cta_click",
        {"trigger": trigger, "product_code": product_code},
    )


async def maybe_grant_premium_preview(
    session: AsyncSession,
    conversation: Conversation,
) -> list[tuple[int, datetime]]:
    """Grant one 24h Premium Preview per user after their first real conversation."""
    if not settings.premium_preview_enabled:
        return []

    quality = (
        await session.execute(
            select(ConversationQuality).where(
                ConversationQuality.conversation_id == conversation.id
            )
        )
    ).scalar_one_or_none()
    if not quality or quality.user1_messages < 1 or quality.user2_messages < 1:
        return []

    users = []
    for user_id in (conversation.user1_id, conversation.user2_id):
        user = await session.get(User, user_id)
        if user:
            users.append(user)

    now = datetime.now(timezone.utc)
    granted: list[tuple[int, datetime]] = []
    for user in users:
        # Subscription/pass/preview already active: do not overwrite its duration.
        if user.premium_until and user.premium_until > now:
            continue

        already = (
            await session.execute(
                select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.user_id == user.id,
                    AnalyticsEvent.event_name == "premium_preview_granted",
                )
            )
        ).scalar_one()
        if int(already or 0) > 0:
            continue

        previous_paid_premium = (
            await session.execute(
                select(func.count(StarTransaction.id))
                .join(Order, Order.id == StarTransaction.order_id)
                .where(
                    StarTransaction.user_id == user.id,
                    Order.product_code.in_(PREMIUM_PRODUCTS),
                )
            )
        ).scalar_one()
        if int(previous_paid_premium or 0) > 0:
            continue

        until = now + timedelta(hours=max(1, settings.premium_preview_hours))
        user.premium_until = until
        await track_event(
            session,
            user,
            "premium_preview_granted",
            {
                "conversation_id": conversation.id,
                "hours": max(1, settings.premium_preview_hours),
                "expires_at": until.isoformat(),
            },
        )
        granted.append((user.telegram_id, until))

    if granted:
        await session.commit()
    return granted


@dataclass(slots=True)
class MonetizationStage:
    key: str
    label: str
    users: int


@dataclass(slots=True)
class TriggerPerformance:
    trigger: str
    label: str
    views: int
    clicks: int
    buyers: int


@dataclass(slots=True)
class MonetizationReport:
    days: int
    since: datetime
    until: datetime
    stages: list[MonetizationStage]
    triggers: list[TriggerPerformance]
    preview_users: int
    monthly_buyers: int
    pass_buyers: int
    stars: int


def _metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


async def build_monetization_report(
    session: AsyncSession,
    *,
    days: int = 7,
) -> MonetizationReport:
    days = 30 if days == 30 else 7
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    names = {
        "premium_paywall_view",
        "premium_cta_click",
        "invoice_created",
        "precheckout_approved",
        "purchase_success",
        "premium_preview_granted",
    }

    rows = (
        await session.execute(
            select(
                AnalyticsEvent.user_id,
                AnalyticsEvent.event_name,
                AnalyticsEvent.metadata_json,
            ).where(
                AnalyticsEvent.created_at >= since,
                AnalyticsEvent.created_at < until,
                AnalyticsEvent.event_name.in_(names),
            )
        )
    ).all()

    stage_sets = {
        "view": set(),
        "click": set(),
        "invoice": set(),
        "precheckout": set(),
        "purchase": set(),
        "preview": set(),
    }
    trigger_sets: dict[str, dict[str, set[str]]] = {}

    for user_id, event_name, raw in rows:
        if not user_id:
            continue
        meta = _metadata(raw)
        product = str(meta.get("product_code") or "")
        trigger = str(meta.get("trigger") or "other")

        if event_name == "premium_paywall_view":
            stage_sets["view"].add(user_id)
            trigger_sets.setdefault(trigger, {"views": set(), "clicks": set(), "buyers": set()})["views"].add(user_id)
        elif event_name == "premium_cta_click" and product in PREMIUM_PRODUCTS:
            stage_sets["click"].add(user_id)
            trigger_sets.setdefault(trigger, {"views": set(), "clicks": set(), "buyers": set()})["clicks"].add(user_id)
        elif event_name == "invoice_created" and product in PREMIUM_PRODUCTS:
            stage_sets["invoice"].add(user_id)
        elif event_name == "precheckout_approved" and product in PREMIUM_PRODUCTS:
            stage_sets["precheckout"].add(user_id)
        elif event_name == "purchase_success" and product in PREMIUM_PRODUCTS:
            stage_sets["purchase"].add(user_id)
            trigger_sets.setdefault(trigger, {"views": set(), "clicks": set(), "buyers": set()})["buyers"].add(user_id)
        elif event_name == "premium_preview_granted":
            stage_sets["preview"].add(user_id)

    product_rows = (
        await session.execute(
            select(
                Order.product_code,
                func.count(func.distinct(StarTransaction.user_id)),
                func.coalesce(func.sum(StarTransaction.stars_amount), 0),
            )
            .join(StarTransaction, StarTransaction.order_id == Order.id)
            .where(
                StarTransaction.created_at >= since,
                StarTransaction.created_at < until,
                Order.product_code.in_(PREMIUM_PRODUCTS),
            )
            .group_by(Order.product_code)
        )
    ).all()
    product_map = {str(code): (int(buyers or 0), int(stars or 0)) for code, buyers, stars in product_rows}

    triggers = [
        TriggerPerformance(
            trigger=trigger,
            label=trigger_label(trigger),
            views=len(data["views"]),
            clicks=len(data["clicks"]),
            buyers=len(data["buyers"]),
        )
        for trigger, data in trigger_sets.items()
    ]
    triggers.sort(key=lambda item: (item.views, item.clicks), reverse=True)

    return MonetizationReport(
        days=days,
        since=since,
        until=until,
        stages=[
            MonetizationStage("view", "Paywall mostrado", len(stage_sets["view"])),
            MonetizationStage("click", "Pulsó comprar", len(stage_sets["click"])),
            MonetizationStage("invoice", "Factura preparada", len(stage_sets["invoice"])),
            MonetizationStage("precheckout", "Pre-checkout aprobado", len(stage_sets["precheckout"])),
            MonetizationStage("purchase", "Compra completada", len(stage_sets["purchase"])),
        ],
        triggers=triggers,
        preview_users=len(stage_sets["preview"]),
        monthly_buyers=product_map.get("premium_monthly", (0, 0))[0],
        pass_buyers=product_map.get("frexo_pass_7d", (0, 0))[0],
        stars=sum(value[1] for value in product_map.values()),
    )


def render_monetization_report(report: MonetizationReport) -> str:
    lines = [
        f"🧲 <b>Monetización FreXo · Últimos {report.days} días</b>",
        "",
        "<b>Embudo Premium / Pass</b>",
    ]
    previous = None
    for index, stage in enumerate(report.stages, start=1):
        if previous is None:
            rate = "100%" if stage.users else "0%"
        else:
            rate = f"{(stage.users / previous * 100):.1f}%" if previous else "0%"
        lines.append(f"{index}. {stage.label}: <b>{stage.users}</b> · {rate} del paso anterior")
        previous = stage.users

    lines += [
        "",
        "<b>Producto</b>",
        f"👑 Premium mensual: <b>{report.monthly_buyers}</b> compradores",
        f"✨ Pass 7 días: <b>{report.pass_buyers}</b> compradores",
        f"⭐ Stars Premium/Pass: <b>{report.stars}</b>",
        "",
        f"🎁 Premium Preview otorgado: <b>{report.preview_users}</b> usuarios",
    ]

    if report.triggers:
        lines += ["", "<b>Rendimiento por contexto</b>"]
        for item in report.triggers[:8]:
            click_rate = item.clicks / item.views * 100 if item.views else 0.0
            buy_rate = item.buyers / item.views * 100 if item.views else 0.0
            lines.append(
                f"• <b>{item.label}</b>: {item.views} vistas → {item.clicks} clics "
                f"({click_rate:.1f}%) → {item.buyers} compras ({buy_rate:.1f}%)"
            )
    else:
        lines += ["", "Aún no hay suficientes eventos de monetización en este periodo."]

    if report.stages[0].users:
        lines += ["", "<b>Lectura rápida</b>"]
        view = report.stages[0].users
        click = report.stages[1].users
        invoice = report.stages[2].users
        purchase = report.stages[4].users
        if click / view < 0.05:
            lines.append("⚠️ La mayor señal está en el paywall: pocos usuarios intentan comprar. Revisa propuesta de valor/copy/contexto.")
        elif invoice and purchase / invoice < 0.40:
            lines.append("⚠️ Hay intención de compra, pero poca finalización. Revisa precio, confianza, saldo de Stars y checkout.")
        elif purchase:
            lines.append("✅ Ya existen compradores. Compara triggers para concentrar la oferta donde mejor convierte.")
        else:
            lines.append("ℹ️ Aún no hay compras; usa este embudo para localizar exactamente dónde se pierde la intención.")

    return "\n".join(lines)
