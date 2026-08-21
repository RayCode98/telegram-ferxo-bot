from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.keyboards import admin_menu, admin_report_actions
from app.models import (
    Conversation,
    Report,
    ReportReview,
    StarTransaction,
    User,
    UserRestriction,
)
from app.repositories import get_user_by_id, get_user_by_telegram
from app.services.matchmaking import clear_active_pair, get_active_partner
from app.services.security import apply_restriction, lift_restrictions


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
        "<code>/ban TELEGRAM_ID 24 motivo</code>\n"
        "<code>/ban TELEGRAM_ID perm motivo</code>\n"
        "<code>/unban TELEGRAM_ID</code>",
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_30d = now - timedelta(days=30)

    async with SessionLocal() as session:
        users = (await session.execute(
            select(func.count(User.id))
        )).scalar_one()

        active_conversations = (await session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status == "active"
            )
        )).scalar_one()

        reports_24h = (await session.execute(
            select(func.count(Report.id)).where(
                Report.created_at >= since_24h
            )
        )).scalar_one()

        premium_active = (await session.execute(
            select(func.count(User.id)).where(
                User.premium_until > now
            )
        )).scalar_one()

        stars_30d = (await session.execute(
            select(func.coalesce(func.sum(StarTransaction.stars_amount), 0)).where(
                StarTransaction.created_at >= since_30d
            )
        )).scalar_one()

        temp_bans = (await session.execute(
            select(func.count(UserRestriction.id)).where(
                UserRestriction.active.is_(True),
                UserRestriction.expires_at > now,
            )
        )).scalar_one()

    await callback.answer()
    await callback.message.answer(
        "📊 <b>FreXo · Estadísticas</b>\n\n"
        f"👥 Usuarios: <b>{users}</b>\n"
        f"💬 Conversaciones activas: <b>{active_conversations}</b>\n"
        f"👑 Premium activos: <b>{premium_active}</b>\n"
        f"🚨 Reportes últimas 24 h: <b>{reports_24h}</b>\n"
        f"⏳ Restricciones temporales: <b>{temp_bans}</b>\n"
        f"⭐ Stars cobradas últimos 30 días: <b>{stars_30d}</b>"
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
