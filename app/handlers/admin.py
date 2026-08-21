from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.keyboards import (
    admin_daily_report_keyboard,
    admin_menu,
    admin_report_actions,
)
from app.models import (
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
