from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.keyboards import (
    admin_acquisition_home_keyboard,
    admin_campaign_detail_keyboard,
    admin_campaign_list_keyboard,
    admin_campaigns_home_keyboard,
    admin_daily_report_keyboard,
    admin_global_stats_keyboard,
    admin_menu,
    admin_report_actions,
)
from app.models import (
    AcquisitionCampaign,
    GrowthProfile,
    Referral,
    Conversation,
    Report,
    ReportReview,
    StarTransaction,
    User,
    UserRestriction,
    Order,
    PaymentRefund,
    SubscriptionState,
)
from app.repositories import get_user_by_id, get_user_by_telegram
from app.services.matchmaking import clear_active_pair, get_active_partner
from app.services.security import apply_restriction, lift_restrictions
from app.services.daily_report import build_daily_report, render_daily_report
from app.states import AdminAcquisition
from app.services.acquisition import (
    campaign_stats,
    create_campaign,
    get_campaign,
    list_campaigns,
    set_campaign_active,
    user_referral_admin_stats,
    valid_campaign_code,
)
from app.services.growth import get_growth_profile


router = Router(name="admin")


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admins


async def require_admin_message(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        return False
    return True


async def require_admin_callback(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer("No autorizado.", show_alert=True)
        return False
    return True


@router.message(Command("admin"))
async def admin_home(message: Message) -> None:
    if not await require_admin_message(message):
        return

    await message.answer(
        "🛡️ <b>Panel de administración de FreXo</b>\n\n"
        "Comandos adicionales:\n"
        "<code>/userinfo TELEGRAM_ID</code>\n"
        "<code>/refstats TELEGRAM_ID</code>\n"
        "<code>/campaigns</code>\n"
        "<code>/ban TELEGRAM_ID 24 motivo</code>\n"
        "<code>/ban TELEGRAM_ID perm motivo</code>\n"
        "<code>/unban TELEGRAM_ID</code>",
        reply_markup=admin_menu(),
    )



@router.callback_query(F.data == "admin:home")
async def admin_home_callback(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    await callback.answer()
    await callback.message.answer(
        "🛡️ <b>Panel de administración de FreXo</b>",
        reply_markup=admin_menu(),
    )


async def _send_daily_report(message: Message) -> None:
    async with SessionLocal() as session:
        report = await build_daily_report(session)

    await message.answer(
        render_daily_report(report),
        reply_markup=admin_daily_report_keyboard(),
    )


@router.callback_query(F.data == "admin:daily")
async def admin_daily_report(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    async with SessionLocal() as session:
        report = await build_daily_report(session)

    await callback.answer("Reporte actualizado")
    text = render_daily_report(report)

    # Si el mismo mensaje ya era el reporte, lo actualizamos en lugar de
    # generar copias. Si viene del panel /admin, enviamos uno nuevo.
    if (
        callback.message.text
        and callback.message.text.startswith("📅 HOY EN FREXO")
    ):
        try:
            await callback.message.edit_text(
                text,
                reply_markup=admin_daily_report_keyboard(),
            )
            return
        except Exception:
            pass

    await callback.message.answer(
        text,
        reply_markup=admin_daily_report_keyboard(),
    )


@router.message(Command("daily"))
async def admin_daily_report_command(message: Message) -> None:
    if not await require_admin_message(message):
        return

    await _send_daily_report(message)



@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_30d = now - timedelta(days=30)

    def pct(value: int, total: int) -> float:
        return (value / total * 100.0) if total else 0.0

    gender_names = {
        "male": ("👨", "Hombres"),
        "female": ("👩", "Mujeres"),
        "other": ("🧑", "Otro"),
        None: ("❔", "Sin definir"),
    }
    seeking_names = {
        "male": ("👨", "Hombres"),
        "female": ("👩", "Mujeres"),
        "other": ("🧑", "Otro"),
        "any": ("✨", "Cualquier género"),
        None: ("❔", "Sin definir"),
    }

    async with SessionLocal() as session:
        users = int((await session.execute(
            select(func.count(User.id))
        )).scalar_one() or 0)

        completed_profiles = int((await session.execute(
            select(func.count(User.id)).where(
                User.onboarding_completed.is_(True)
            )
        )).scalar_one() or 0)

        gender_rows = (await session.execute(
            select(User.gender, func.count(User.id))
            .where(User.onboarding_completed.is_(True))
            .group_by(User.gender)
        )).all()
        gender_counts = {key: int(value) for key, value in gender_rows}

        seeking_rows = (await session.execute(
            select(User.seeking_gender, func.count(User.id))
            .where(User.onboarding_completed.is_(True))
            .group_by(User.seeking_gender)
        )).all()
        seeking_counts = {key: int(value) for key, value in seeking_rows}

        active_conversations = int((await session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == "active"
            )
        )).scalar_one() or 0)

        reports_24h = int((await session.execute(
            select(func.count(Report.id)).where(
                Report.created_at >= since_24h
            )
        )).scalar_one() or 0)

        premium_active = int((await session.execute(
            select(func.count(User.id)).where(
                User.premium_until > now
            )
        )).scalar_one() or 0)

        stars_30d = int((await session.execute(
            select(func.coalesce(func.sum(StarTransaction.stars_amount), 0)).where(
                StarTransaction.created_at >= since_30d
            )
        )).scalar_one() or 0)

        temp_bans = int((await session.execute(
            select(func.count(UserRestriction.id)).where(
                UserRestriction.active.is_(True),
                UserRestriction.expires_at > now,
            )
        )).scalar_one() or 0)

    gender_total = sum(gender_counts.values())
    seeking_total = sum(seeking_counts.values())

    gender_lines: list[str] = []
    for key in ("male", "female", "other", None):
        count = gender_counts.get(key, 0)
        if count or key in {"male", "female"}:
            emoji, label = gender_names[key]
            gender_lines.append(
                f"{emoji} {label}: <b>{count}</b> ({pct(count, gender_total):.1f}%)"
            )

    seeking_lines: list[str] = []
    for key in ("female", "male", "other", "any", None):
        count = seeking_counts.get(key, 0)
        if count or key in {"female", "male", "any"}:
            emoji, label = seeking_names[key]
            seeking_lines.append(
                f"{emoji} Buscan {label.lower()}: <b>{count}</b> "
                f"({pct(count, seeking_total):.1f}%)"
            )

    dominant_key = None
    dominant_count = 0
    if seeking_counts:
        dominant_key, dominant_count = max(
            seeking_counts.items(),
            key=lambda item: item[1],
        )

    if dominant_key in seeking_names and seeking_total:
        dominant_emoji, dominant_label = seeking_names[dominant_key]
        dominant_line = (
            f"🏆 <b>Opción más elegida:</b> {dominant_emoji} "
            f"{dominant_label} — <b>{pct(dominant_count, seeking_total):.1f}%</b>"
        )
    else:
        dominant_line = "🏆 <b>Opción más elegida:</b> todavía sin datos suficientes."

    specific_counts = {
        key: seeking_counts.get(key, 0)
        for key in ("male", "female", "other")
    }
    specific_total = sum(specific_counts.values())
    specific_key = None
    specific_count = 0
    if specific_total:
        specific_key, specific_count = max(
            specific_counts.items(),
            key=lambda item: item[1],
        )

    if specific_key in seeking_names and specific_total:
        specific_emoji, specific_label = seeking_names[specific_key]
        specific_line = (
            f"🎯 <b>Género específico más buscado:</b> {specific_emoji} "
            f"{specific_label} — <b>{pct(specific_count, specific_total):.1f}%</b> "
            "de quienes eligieron un género específico."
        )
    else:
        specific_line = (
            "🎯 <b>Género específico más buscado:</b> "
            "todavía sin datos suficientes."
        )

    text = (
        "📊 <b>FreXo · Estadísticas globales</b>\n\n"
        f"👥 Usuarios registrados: <b>{users}</b>\n"
        f"✅ Perfiles completados: <b>{completed_profiles}</b>\n"
        f"💬 Conversaciones activas: <b>{active_conversations}</b>\n"
        f"👑 Premium activos: <b>{premium_active}</b>\n"
        f"🚨 Reportes últimas 24 h: <b>{reports_24h}</b>\n"
        f"⏳ Restricciones temporales: <b>{temp_bans}</b>\n"
        f"⭐ Stars cobradas últimos 30 días: <b>{stars_30d}</b>\n\n"
        "<b>🚻 Distribución por género</b>\n"
        + "\n".join(gender_lines)
        + "\n\n"
        "<b>❤️ ¿Qué género buscan?</b>\n"
        + "\n".join(seeking_lines)
        + "\n\n"
        + dominant_line
        + "\n"
        + specific_line
        + "\n\n"
        "<i>Los porcentajes de género y preferencias se calculan sobre perfiles "
        "que completaron el registro.</i>"
    )

    await callback.answer("Estadísticas actualizadas")

    if callback.message.text and callback.message.text.startswith(
        "📊 FreXo · Estadísticas globales"
    ):
        try:
            await callback.message.edit_text(
                text,
                reply_markup=admin_global_stats_keyboard(),
            )
            return
        except Exception:
            pass

    await callback.message.answer(
        text,
        reply_markup=admin_global_stats_keyboard(),
    )


@router.callback_query(F.data == "admin:reports")
async def admin_reports(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    async with SessionLocal() as session:
        reviewed_subq = select(ReportReview.report_id)
        result = await session.execute(
            select(Report)
            .where(Report.id.not_in(reviewed_subq))
            .order_by(Report.created_at.desc())
            .limit(10)
        )
        reports = list(result.scalars())

        if not reports:
            await callback.answer()
            await callback.message.answer("✅ No hay reportes pendientes.")
            return

        await callback.answer()
        await callback.message.answer(
            f"🚨 <b>{len(reports)} reportes pendientes recientes</b>"
        )

        for report in reports:
            reporter = await get_user_by_id(session, report.reporter_id)
            reported = await get_user_by_id(session, report.reported_id)
            if not reported:
                continue

            await callback.message.answer(
                "🚨 <b>Reporte</b>\n\n"
                f"Motivo: <code>{report.reason}</code>\n"
                f"Reportado: <b>{reported.alias or 'Sin alias'}</b>\n"
                f"Telegram ID: <code>{reported.telegram_id}</code>\n"
                f"Reportante: <code>{reporter.telegram_id if reporter else '?'}</code>\n"
                f"Fecha: {report.created_at}",
                reply_markup=admin_report_actions(report.id),
            )


@router.callback_query(F.data.startswith("admin:dismiss:"))
async def admin_dismiss(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    report_id = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        session.add(
            ReportReview(
                report_id=report_id,
                status="reviewed",
                admin_telegram_id=callback.from_user.id,
                note="Sin sanción",
            )
        )
        await session.commit()

    await callback.answer("Reporte revisado")
    await callback.message.edit_reply_markup(reply_markup=None)


async def _ban_from_report(
    callback: CallbackQuery,
    *,
    hours: int | None,
) -> None:
    if not await require_admin_callback(callback):
        return

    report_id = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        report = await session.get(Report, report_id)
        if not report:
            await callback.answer("Reporte no encontrado.", show_alert=True)
            return

        target = await get_user_by_id(session, report.reported_id)
        if not target:
            await callback.answer("Usuario no encontrado.", show_alert=True)
            return

        expires = (
            datetime.now(timezone.utc) + timedelta(hours=hours)
            if hours is not None
            else None
        )
        await apply_restriction(
            session,
            target,
            admin_telegram_id=callback.from_user.id,
            reason="Sanción por reporte revisado",
            expires_at=expires,
            permanent=hours is None,
        )
        session.add(
            ReportReview(
                report_id=report_id,
                status="sanctioned",
                admin_telegram_id=callback.from_user.id,
                note="Ban permanente" if hours is None else f"Ban {hours} h",
            )
        )
        await session.commit()

    active = await get_active_partner(target.telegram_id)
    if active:
        partner_tg, _ = active
        await clear_active_pair(target.telegram_id, partner_tg)
        await callback.bot.send_message(
            partner_tg,
            "🤖 <b>FreXo</b>\n\nLa conversación terminó por una acción de moderación.",
        )

    try:
        await callback.bot.send_message(
            target.telegram_id,
            "⛔ <b>FreXo aplicó una restricción a tu cuenta.</b>\n\n"
            + ("Duración: 24 horas." if hours else "La restricción es permanente.")
        )
    except Exception:
        pass

    await callback.answer("Sanción aplicada")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:ban24:"))
async def admin_ban24(callback: CallbackQuery) -> None:
    await _ban_from_report(callback, hours=24)


@router.callback_query(F.data.startswith("admin:banperm:"))
async def admin_banperm(callback: CallbackQuery) -> None:
    await _ban_from_report(callback, hours=None)


async def _render_referral_user_stats(
    session,
    user: User,
    bot_username: str,
) -> str:
    stats = await user_referral_admin_stats(session, user)
    growth = await get_growth_profile(session, user)
    await session.commit()
    link = f"https://t.me/{bot_username}?start=ref_{growth.referral_code}"
    alias = html.escape(user.alias or "Sin alias")
    return (
        "👥 <b>Referidos del usuario</b>\n\n"
        f"👤 {alias}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n\n"
        f"🔗 Referidos totales: <b>{stats.total}</b>\n"
        f"✅ Completaron registro: <b>{stats.completed}</b> "
        f"({stats.completion_rate:.1f}%)\n"
        f"🤝 Calificados por primer match: <b>{stats.qualified}</b> "
        f"({stats.qualification_rate:.1f}%)\n"
        f"⏳ Pendientes de primer match: <b>{stats.pending}</b>\n\n"
        "<b>Enlace personal del usuario:</b>\n"
        f"<code>{link}</code>"
    )


@router.callback_query(F.data == "admin:referrals")
async def admin_referrals_lookup(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await require_admin_callback(callback):
        return
    await state.set_state(AdminAcquisition.referral_user_id)
    await callback.answer()
    await callback.message.answer(
        "👥 <b>Consultar referidos de un usuario</b>\n\n"
        "Envíame su <b>Telegram ID</b>.\n\n"
        "Ejemplo: <code>123456789</code>\n"
        "Puedes escribir <code>cancelar</code> para salir.",
        reply_markup=admin_acquisition_home_keyboard(),
    )


@router.message(AdminAcquisition.referral_user_id)
async def admin_referrals_lookup_value(
    message: Message,
    state: FSMContext,
) -> None:
    if not await require_admin_message(message):
        return
    raw = (message.text or "").strip()
    if raw.lower() == "cancelar":
        await state.clear()
        await message.answer("Consulta cancelada.", reply_markup=admin_menu())
        return
    if not raw.isdigit():
        await message.answer("Envíame únicamente el Telegram ID numérico.")
        return

    telegram_id = int(raw)
    me = await message.bot.get_me()
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, telegram_id)
        if not user:
            await message.answer("Usuario no encontrado.")
            return
        text = await _render_referral_user_stats(session, user, me.username)

    await state.clear()
    await message.answer(text, reply_markup=admin_acquisition_home_keyboard())


@router.message(Command("refstats"))
async def admin_refstats_command(
    message: Message,
    command: CommandObject,
) -> None:
    if not await require_admin_message(message):
        return
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Uso: <code>/refstats TELEGRAM_ID</code>")
        return
    me = await message.bot.get_me()
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, int(raw))
        if not user:
            await message.answer("Usuario no encontrado.")
            return
        text = await _render_referral_user_stats(session, user, me.username)
    await message.answer(text, reply_markup=admin_acquisition_home_keyboard())


@router.callback_query(F.data == "admin:campaigns")
async def admin_campaigns_home(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await require_admin_callback(callback):
        return
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "📣 <b>Campañas de adquisición</b>\n\n"
        "Crea enlaces personalizados para saber qué publicación, canal o "
        "campaña está trayendo usuarios reales a FreXo.\n\n"
        "FreXo mide aperturas del bot, usuarios atribuidos, registros "
        "completados y primer match.",
        reply_markup=admin_campaigns_home_keyboard(),
    )


@router.callback_query(F.data == "admin:campaigns:new")
async def admin_campaign_new(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await require_admin_callback(callback):
        return
    await state.set_state(AdminAcquisition.campaign_name)
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Nueva campaña</b>\n\n"
        "Primero escribe un nombre interno.\n"
        "Ejemplo: <code>Facebook agosto</code>"
    )


@router.message(AdminAcquisition.campaign_name)
async def admin_campaign_name(
    message: Message,
    state: FSMContext,
) -> None:
    if not await require_admin_message(message):
        return
    name = (message.text or "").strip()
    if name.lower() == "cancelar":
        await state.clear()
        await message.answer("Creación cancelada.", reply_markup=admin_menu())
        return
    if not 3 <= len(name) <= 80:
        await message.answer("El nombre debe tener entre 3 y 80 caracteres.")
        return
    await state.update_data(campaign_name=name)
    await state.set_state(AdminAcquisition.campaign_code)
    await message.answer(
        "🔗 Ahora escribe el <b>código personalizado</b> del enlace.\n\n"
        "Usa de 3 a 24 caracteres: letras, números, <code>_</code> o "
        "<code>-</code>.\n\n"
        "Ejemplos:\n"
        "<code>facebook_agosto</code>\n"
        "<code>canal_fenix</code>\n"
        "<code>google_mx</code>"
    )


@router.message(AdminAcquisition.campaign_code)
async def admin_campaign_code(
    message: Message,
    state: FSMContext,
) -> None:
    if not await require_admin_message(message):
        return
    code = (message.text or "").strip().lower()
    if code == "cancelar":
        await state.clear()
        await message.answer("Creación cancelada.", reply_markup=admin_menu())
        return
    if not valid_campaign_code(code):
        await message.answer(
            "Código inválido. Usa 3–24 caracteres: A-Z, a-z, 0-9, _ o -."
        )
        return

    data = await state.get_data()
    name = data.get("campaign_name", "Campaña")
    try:
        async with SessionLocal() as session:
            campaign = await create_campaign(
                session,
                name=name,
                code=code,
                admin_telegram_id=message.from_user.id,
            )
    except ValueError:
        await message.answer(
            "Ese código ya existe. Escribe otro código para esta campaña."
        )
        return

    await state.clear()
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=camp_{campaign.code}"
    await message.answer(
        "✅ <b>Campaña creada</b>\n\n"
        f"📣 Nombre: <b>{html.escape(campaign.name)}</b>\n"
        f"🏷 Código: <code>{campaign.code}</code>\n\n"
        "🔗 <b>Enlace personalizado:</b>\n"
        f"<code>{link}</code>\n\n"
        "Ya puedes usar este enlace en anuncios, publicaciones o canales.",
        reply_markup=admin_campaigns_home_keyboard(),
    )


@router.callback_query(F.data == "admin:campaigns:list")
async def admin_campaign_list(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    async with SessionLocal() as session:
        campaigns = await list_campaigns(session, limit=20)
        overview = []
        for campaign in campaigns:
            stats = await campaign_stats(session, campaign)
            overview.append((campaign, stats))

    await callback.answer()
    if not overview:
        await callback.message.answer(
            "📣 Todavía no has creado campañas.",
            reply_markup=admin_campaigns_home_keyboard(),
        )
        return

    lines = ["📊 <b>Campañas de adquisición</b>", ""]
    for campaign, stats in overview:
        icon = "🟢" if campaign.active else "⚪"
        lines.append(
            f"{icon} <b>{html.escape(campaign.name)}</b> · "
            f"{stats.attributed} atribuidos · {stats.qualified} matches"
        )

    keyboard_data = [
        (campaign.code, campaign.name, campaign.active)
        for campaign, _ in overview
    ]
    await callback.message.answer(
        "\n".join(lines),
        reply_markup=admin_campaign_list_keyboard(keyboard_data),
    )


async def _campaign_detail_text(
    campaign: AcquisitionCampaign,
    stats,
    bot_username: str,
) -> str:
    link = f"https://t.me/{bot_username}?start=camp_{campaign.code}"
    status = "🟢 Activa" if campaign.active else "⚪ Pausada"
    return (
        "📣 <b>Detalle de campaña</b>\n\n"
        f"Nombre: <b>{html.escape(campaign.name)}</b>\n"
        f"Código: <code>{campaign.code}</code>\n"
        f"Estado: <b>{status}</b>\n\n"
        "<b>Embudo</b>\n"
        f"▶️ Inicios totales: <b>{stats.starts}</b>\n"
        f"👤 Usuarios únicos que iniciaron: <b>{stats.unique_starts}</b>\n"
        f"🎯 Usuarios atribuidos: <b>{stats.attributed}</b> "
        f"({stats.attribution_rate:.1f}%)\n"
        f"✅ Registro completado: <b>{stats.completed}</b> "
        f"({stats.completion_rate:.1f}%)\n"
        f"🤝 Primer match: <b>{stats.qualified}</b> "
        f"({stats.qualified_rate:.1f}%)\n\n"
        "🔗 <b>Enlace:</b>\n"
        f"<code>{link}</code>"
    )


@router.callback_query(F.data.startswith("admin:camp:"))
async def admin_campaign_detail(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    code = callback.data.split(":", 2)[2]
    async with SessionLocal() as session:
        campaign = await get_campaign(session, code)
        if not campaign:
            await callback.answer("Campaña no encontrada.", show_alert=True)
            return
        stats = await campaign_stats(session, campaign)
    me = await callback.bot.get_me()
    await callback.answer("Actualizado")
    await callback.message.answer(
        await _campaign_detail_text(campaign, stats, me.username),
        reply_markup=admin_campaign_detail_keyboard(
            campaign.code,
            campaign.active,
        ),
    )


@router.callback_query(F.data.startswith("admin:camptoggle:"))
async def admin_campaign_toggle(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    code = callback.data.split(":", 2)[2]
    async with SessionLocal() as session:
        campaign = await get_campaign(session, code)
        if not campaign:
            await callback.answer("Campaña no encontrada.", show_alert=True)
            return
        await set_campaign_active(session, campaign, not campaign.active)
        stats = await campaign_stats(session, campaign)
    me = await callback.bot.get_me()
    await callback.answer("Estado actualizado")
    await callback.message.answer(
        await _campaign_detail_text(campaign, stats, me.username),
        reply_markup=admin_campaign_detail_keyboard(
            campaign.code,
            campaign.active,
        ),
    )


@router.message(Command("campaigns"))
async def admin_campaigns_command(message: Message) -> None:
    if not await require_admin_message(message):
        return
    await message.answer(
        "📣 <b>Campañas de adquisición</b>",
        reply_markup=admin_campaigns_home_keyboard(),
    )


@router.message(Command("userinfo"))
async def user_info(message: Message, command: CommandObject) -> None:
    if not await require_admin_message(message):
        return

    if not command.args or not command.args.strip().isdigit():
        await message.answer("Uso: <code>/userinfo TELEGRAM_ID</code>")
        return

    telegram_id = int(command.args.strip())

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, telegram_id)
        if not user:
            await message.answer("Usuario no encontrado.")
            return

        reports = (await session.execute(
            select(func.count(Report.id)).where(Report.reported_id == user.id)
        )).scalar_one()

    await message.answer(
        "👤 <b>Información de usuario</b>\n\n"
        f"Alias: {user.alias or 'Sin alias'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Onboarding: {'✅' if user.onboarding_completed else '❌'}\n"
        f"Ban permanente: {'⛔' if user.is_banned else 'No'}\n"
        f"Reportes recibidos: <b>{reports}</b>\n"
        f"Premium hasta: {user.premium_until or 'No'}\n"
        f"Creado: {user.created_at}"
    )


@router.message(Command("ban"))
async def ban_user(message: Message, command: CommandObject) -> None:
    if not await require_admin_message(message):
        return

    parts = (command.args or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer(
            "Uso:\n"
            "<code>/ban TELEGRAM_ID 24 motivo</code>\n"
            "<code>/ban TELEGRAM_ID perm motivo</code>"
        )
        return

    telegram_id = int(parts[0])
    duration = parts[1].lower()
    reason = parts[2] if len(parts) >= 3 else "Moderación administrativa"

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, telegram_id)
        if not user:
            await message.answer("Usuario no encontrado.")
            return

        if duration in {"perm", "permanent", "permanente"}:
            expires = None
            permanent = True
        elif duration.isdigit():
            expires = datetime.now(timezone.utc) + timedelta(hours=int(duration))
            permanent = False
        else:
            await message.answer("Duración inválida. Usa horas o <code>perm</code>.")
            return

        await apply_restriction(
            session,
            user,
            admin_telegram_id=message.from_user.id,
            reason=reason,
            expires_at=expires,
            permanent=permanent,
        )

    active = await get_active_partner(telegram_id)
    if active:
        partner_tg, _ = active
        await clear_active_pair(telegram_id, partner_tg)

    await message.answer("✅ Restricción aplicada.")


@router.message(Command("unban"))
async def unban_user(message: Message, command: CommandObject) -> None:
    if not await require_admin_message(message):
        return

    if not command.args or not command.args.strip().isdigit():
        await message.answer("Uso: <code>/unban TELEGRAM_ID</code>")
        return

    telegram_id = int(command.args.strip())

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, telegram_id)
        if not user:
            await message.answer("Usuario no encontrado.")
            return

        await lift_restrictions(
            session,
            user,
            message.from_user.id,
        )

    await message.answer("✅ Restricciones retiradas.")


@router.callback_query(F.data == "admin:active")
async def active_overview(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(func.count(User.id)).where(
                User.last_seen_at >= now - timedelta(minutes=15)
            )
        )
        active_users = result.scalar_one()

    await callback.answer()
    await callback.message.answer(
        f"🟢 Usuarios vistos en los últimos 15 minutos: <b>{active_users}</b>"
    )



@router.callback_query(F.data == "admin:conversion")
async def admin_conversion(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    async with SessionLocal() as session:
        new_users = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= since)
        )).scalar_one()

        purchases = (await session.execute(
            select(func.count(StarTransaction.id)).where(
                StarTransaction.created_at >= since
            )
        )).scalar_one()

        payers = (await session.execute(
            select(func.count(func.distinct(StarTransaction.user_id))).where(
                StarTransaction.created_at >= since
            )
        )).scalar_one()

        matches = (await session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.started_at >= since
            )
        )).scalar_one()

        stars = (await session.execute(
            select(func.coalesce(func.sum(StarTransaction.stars_amount), 0)).where(
                StarTransaction.created_at >= since
            )
        )).scalar_one()

        product_rows = await session.execute(
            select(
                Order.product_code,
                func.count(StarTransaction.id),
                func.sum(StarTransaction.stars_amount),
            )
            .join(StarTransaction, StarTransaction.order_id == Order.id)
            .where(StarTransaction.created_at >= since)
            .group_by(Order.product_code)
            .order_by(func.sum(StarTransaction.stars_amount).desc())
            .limit(8)
        )
        products = list(product_rows.all())

    conversion = (
        (float(payers) / float(new_users) * 100.0)
        if new_users
        else 0.0
    )

    lines = [
        "📈 <b>Conversión · últimos 30 días</b>",
        "",
        f"🆕 Usuarios nuevos: <b>{new_users}</b>",
        f"🤝 Matches: <b>{matches}</b>",
        f"💳 Compras: <b>{purchases}</b>",
        f"👤 Usuarios compradores: <b>{payers}</b>",
        f"⭐ Stars: <b>{stars}</b>",
        f"📊 Conversión a comprador: <b>{conversion:.2f}%</b>",
    ]

    if products:
        lines.extend(["", "<b>Ingresos por producto:</b>"])
        for code, count, product_stars in products:
            lines.append(
                f"• <code>{code}</code>: {count} compras · {product_stars or 0} ⭐"
            )

    await callback.answer()
    await callback.message.answer("\n".join(lines))


@router.callback_query(F.data == "admin:finance")
async def admin_finance(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    balance = await callback.bot.get_my_star_balance()
    telegram_txs = await callback.bot.get_star_transactions(offset=0, limit=10)

    async with SessionLocal() as session:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        local_30d = (await session.execute(
            select(func.coalesce(func.sum(StarTransaction.stars_amount), 0)).where(
                StarTransaction.created_at >= since
            )
        )).scalar_one()
        refunds_30d = (await session.execute(
            select(func.coalesce(func.sum(PaymentRefund.stars_amount), 0)).where(
                PaymentRefund.refunded_at >= since
            )
        )).scalar_one()

    lines = [
        "💰 <b>Finanzas FreXo</b>",
        "",
        f"⭐ Balance Telegram: <b>{balance.amount}</b>",
        f"📥 Cobrado local 30 días: <b>{local_30d} ⭐</b>",
        f"↩️ Reembolsado 30 días: <b>{refunds_30d} ⭐</b>",
        "",
        "<b>Últimos movimientos Telegram:</b>",
    ]
    for tx in telegram_txs.transactions[:10]:
        direction = "📥" if tx.source is not None else "📤"
        lines.append(
            f"{direction} {tx.amount} ⭐ · <code>{tx.id}</code> · {tx.date:%d/%m %H:%M}"
        )

    lines.extend([
        "",
        "Reembolso administrativo:",
        "<code>/refund CHARGE_ID motivo</code>",
    ])
    await callback.answer()
    await callback.message.answer("\n".join(lines))


@router.message(Command("refund"))
async def refund_payment(message: Message, command: CommandObject) -> None:
    if not await require_admin_message(message):
        return

    parts = (command.args or "").split(maxsplit=1)
    if not parts:
        await message.answer("Uso: <code>/refund CHARGE_ID motivo</code>")
        return

    charge_id = parts[0]
    reason = parts[1] if len(parts) > 1 else "Reembolso administrativo"

    async with SessionLocal() as session:
        transaction = (await session.execute(
            select(StarTransaction).where(
                StarTransaction.telegram_payment_charge_id == charge_id
            )
        )).scalar_one_or_none()
        if not transaction:
            await message.answer("Transacción local no encontrada.")
            return

        already = (await session.execute(
            select(PaymentRefund.id).where(
                PaymentRefund.telegram_payment_charge_id == charge_id
            )
        )).scalar_one_or_none()
        if already:
            await message.answer("Esta transacción ya figura como reembolsada.")
            return

        user = await session.get(User, transaction.user_id)
        order = await session.get(Order, transaction.order_id)
        if not user or not order:
            await message.answer("No se pudo resolver usuario/orden.")
            return

        tx_id = transaction.id
        user_id = user.id
        telegram_user_id = user.telegram_id
        stars_amount = transaction.stars_amount
        product_code = order.product_code
        sub = (await session.execute(
            select(SubscriptionState).where(
                SubscriptionState.user_id == user.id,
                SubscriptionState.product_code == "premium_monthly",
            )
        )).scalar_one_or_none()
        subscription_charge = sub.telegram_payment_charge_id if sub else None

    await message.bot.refund_star_payment(
        user_id=telegram_user_id,
        telegram_payment_charge_id=charge_id,
    )

    if product_code == "premium_monthly" and subscription_charge:
        try:
            await message.bot.edit_user_star_subscription(
                user_id=telegram_user_id,
                telegram_payment_charge_id=subscription_charge,
                is_canceled=True,
            )
        except Exception:
            pass

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        session.add(PaymentRefund(
            star_transaction_id=tx_id,
            user_id=user_id,
            telegram_payment_charge_id=charge_id,
            stars_amount=stars_amount,
            admin_telegram_id=message.from_user.id,
            reason=reason[:255],
        ))
        if product_code == "premium_monthly" and user:
            user.premium_until = datetime.now(timezone.utc)
            sub = (await session.execute(
                select(SubscriptionState).where(
                    SubscriptionState.user_id == user.id,
                    SubscriptionState.product_code == "premium_monthly",
                )
            )).scalar_one_or_none()
            if sub:
                sub.state = "refunded"
                sub.auto_renew_enabled = False
        await session.commit()

    try:
        await message.bot.send_message(
            telegram_user_id,
            f"↩️ <b>Tu compra de {stars_amount} Stars fue reembolsada.</b>\n\n"
            f"Referencia: <code>{charge_id}</code>"
        )
    except Exception:
        pass

    await message.answer("✅ Reembolso procesado y auditado.")
