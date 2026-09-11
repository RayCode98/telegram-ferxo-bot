from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.types import (
    BotSubscriptionUpdated,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)

from app.config import settings
from app.database import SessionLocal
from app.keyboards import premium_offer_keyboard, store_keyboard
from app.repositories import get_user_by_telegram
from app.services.monetization import (
    record_paywall_click,
    record_paywall_view,
    render_premium_offer,
)
from app.services.payments import (
    create_order,
    fulfill_successful_payment,
    send_product_invoice,
    validate_pre_checkout,
)
from app.services.products import PRODUCTS
from app.services.subscriptions import apply_subscription_update, get_subscription_state

router = Router(name="payments")


def premium_manage_keyboard(auto_renew_enabled: bool, *, subscription: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if subscription:
        rows.append([
            InlineKeyboardButton(
                text="⏹ Cancelar renovación" if auto_renew_enabled else "▶️ Reactivar renovación",
                callback_data="premium:cancel_renewal" if auto_renew_enabled else "premium:resume_renewal",
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="👑 Ver Premium mensual",
                callback_data="premium:offer:premium_menu",
            )
        ])
    rows.extend([
        [InlineKeyboardButton(text="⭐ Ver tienda", callback_data="premium:store")],
        [InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_offer(message: Message, trigger: str, *, likes_count: int = 0) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        await record_paywall_view(session, user, trigger, likes_count=likes_count or None)
        await session.commit()
    await message.answer(
        render_premium_offer(trigger, likes_count=likes_count),
        reply_markup=premium_offer_keyboard(trigger),
    )


@router.message(F.text == "👑 Premium")
async def premium_store(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        state = await get_subscription_state(session, user) if user else None
    now = datetime.now(timezone.utc)
    if user and user.premium_until and user.premium_until > now:
        if state and state.telegram_payment_charge_id:
            renew = state.auto_renew_enabled
            await message.answer(
                "👑 <b>FreXo Premium</b>\n\n"
                "Estado: <b>✅ Activo</b>\n"
                f"Vigente hasta: <b>{user.premium_until.strftime('%d/%m/%Y %H:%M UTC')}</b>\n"
                f"Renovación automática: <b>{'Sí' if renew else 'No'}</b>",
                reply_markup=premium_manage_keyboard(renew, subscription=True),
            )
        else:
            await message.answer(
                "✨ <b>Premium temporal activo</b>\n\n"
                f"Tus beneficios están disponibles hasta <b>{user.premium_until.strftime('%d/%m/%Y %H:%M UTC')}</b>.\n\n"
                "Puedes disfrutarlo hasta el final o convertirte en Premium mensual.",
                reply_markup=premium_manage_keyboard(False, subscription=False),
            )
        return
    await _send_offer(message, "premium_menu")


@router.callback_query(F.data.startswith("premium:offer:"))
async def open_contextual_offer(callback: CallbackQuery) -> None:
    trigger = callback.data.split(":", 2)[2][:24] or "other"
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            await callback.answer("Usa /start primero.", show_alert=True)
            return
        await record_paywall_view(session, user, trigger)
        await session.commit()
    await callback.answer()
    await callback.message.answer(
        render_premium_offer(trigger),
        reply_markup=premium_offer_keyboard(trigger),
    )


@router.callback_query(F.data == "premium:store")
async def open_store(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if user:
            await record_paywall_view(session, user, "store")
            await session.commit()
    await callback.answer()
    await callback.message.answer(
        "⭐ <b>FreXo Store</b>\n\n"
        "La tienda completa reúne productos opcionales. Hablar, bloquear, reportar y terminar una conversación siguen siendo gratuitos.",
        reply_markup=store_keyboard(),
    )


async def _set_renewal(callback: CallbackQuery, canceled: bool) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        state = await get_subscription_state(session, user)
        if not state or not state.telegram_payment_charge_id:
            await callback.answer("No encontramos una suscripción administrable.", show_alert=True)
            return
        charge = state.telegram_payment_charge_id
    await callback.bot.edit_user_star_subscription(
        user_id=callback.from_user.id,
        telegram_payment_charge_id=charge,
        is_canceled=canceled,
    )
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        state = await get_subscription_state(session, user)
        if state:
            state.auto_renew_enabled = not canceled
            state.state = "canceled" if canceled else "active"
            await session.commit()
    await callback.answer("Renovación actualizada")
    await callback.message.answer(
        "✅ La renovación automática quedó "
        + ("cancelada." if canceled else "reactivada.")
        + "\n\nTu Premium actual sigue vigente hasta su fecha de expiración."
    )


@router.callback_query(F.data == "premium:cancel_renewal")
async def cancel(callback: CallbackQuery) -> None:
    await _set_renewal(callback, True)


@router.callback_query(F.data == "premium:resume_renewal")
async def resume(callback: CallbackQuery) -> None:
    await _set_renewal(callback, False)


@router.callback_query(F.data.startswith("buyctx:"))
async def buy_contextual_product(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return
    code, trigger = parts[1], parts[2][:24]
    if code not in {"premium_monthly", "frexo_pass_7d"}:
        await callback.answer("Producto no disponible.", show_alert=True)
        return
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            await callback.answer("Usa /start primero.", show_alert=True)
            return
        await record_paywall_click(session, user, trigger, code)
        order = await create_order(
            session,
            user,
            code,
            context_type="paywall",
            context_value=trigger,
        )
    await callback.answer()
    await send_product_invoice(callback.bot, callback.from_user.id, order)


@router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    if code not in PRODUCTS:
        await callback.answer("Producto no disponible.", show_alert=True)
        return
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            await callback.answer("Usa /start primero.", show_alert=True)
            return
        if code in {"premium_monthly", "frexo_pass_7d"}:
            # Some legacy product panels display store_keyboard() directly.
            # Record a synthetic store exposure so the monetization funnel
            # remains internally consistent when the user chooses Premium.
            await record_paywall_view(session, user, "store")
            await record_paywall_click(session, user, "store", code)
            context_type = "paywall"
        else:
            context_type = "store"
        order = await create_order(
            session,
            user,
            code,
            context_type=context_type,
            context_value="store",
        )
    await callback.answer()
    await send_product_invoice(callback.bot, callback.from_user.id, order)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    async with SessionLocal() as session:
        ok, error = await validate_pre_checkout(session, query)
    await query.answer(ok=ok, error_message=error)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    try:
        async with SessionLocal() as session:
            result = await fulfill_successful_payment(session, message)
        await message.answer("✅ <b>Pago recibido correctamente.</b>\n\n" + result.text)
        if result.notify_telegram_id and result.notify_text:
            await message.bot.send_message(result.notify_telegram_id, result.notify_text)
    except Exception:
        await message.answer(
            "⚠️ El pago fue recibido, pero ocurrió un problema al acreditar el beneficio. "
            "Usa /paysupport para que podamos revisarlo."
        )
        raise


@router.subscription()
async def subscription_updated(event: BotSubscriptionUpdated, bot: Bot) -> None:
    async with SessionLocal() as session:
        user, state = await apply_subscription_update(session, event)
    if not user or not state:
        return
    text = {
        "canceled": "👑 <b>Renovación de Premium cancelada.</b>\n\nTu acceso actual permanece activo hasta su fecha de expiración.",
        "active": "👑 <b>Renovación de Premium reactivada.</b>",
        "failed": "⚠️ <b>No se pudo renovar FreXo Premium.</b>\n\nRevisa tu saldo de Telegram Stars si deseas continuar con la suscripción.",
    }.get(event.state, f"👑 Estado de suscripción actualizado: {event.state}")
    try:
        await bot.send_message(user.telegram_id, text)
    except Exception:
        pass


@router.message(F.text == "/paysupport")
async def pay_support(message: Message) -> None:
    await message.answer(
        "💳 <b>Soporte de pagos</b>\n\n"
        "Si tuviste un problema con Stars o con un beneficio comprado, contacta a "
        + settings.support_username
        + f" e indica tu ID de Telegram: <code>{message.from_user.id}</code>.\n\n"
        "No envíes contraseñas, códigos de acceso ni datos bancarios."
    )
