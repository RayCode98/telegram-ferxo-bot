from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, StarTransaction, User
from app.repositories import (
    add_consumable,
    find_order_by_payload,
    transaction_exists,
)
from app.services.products import PRODUCTS


async def create_order(
    session: AsyncSession,
    user: User,
    product_code: str,
) -> Order:
    product = PRODUCTS[product_code]
    payload = f"frexo:{product_code}:{uuid.uuid4().hex}"

    order = Order(
        user_id=user.id,
        product_code=product_code,
        stars_amount=product.stars,
        invoice_payload=payload,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def send_product_invoice(
    bot: Bot,
    chat_id: int,
    order: Order,
) -> None:
    product = PRODUCTS[order.product_code]
    prices = [LabeledPrice(label=product.title, amount=product.stars)]

    # Telegram no admite subscription_period en sendInvoice.
    # Las suscripciones recurrentes se crean con createInvoiceLink.
    if product.subscription_period:
        invoice_link = await bot.create_invoice_link(
            title=product.title,
            description=product.description,
            payload=order.invoice_payload,
            currency="XTR",
            prices=prices,
            provider_token="",
            subscription_period=product.subscription_period,
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"⭐ Suscribirme por {product.stars} Stars",
                        url=invoice_link,
                    )
                ]
            ]
        )

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "👑 <b>FreXo Premium</b>\n\n"
                f"Precio: <b>{product.stars} ⭐ cada 30 días</b>\n\n"
                "La suscripción se renovará automáticamente cada 30 días "
                "mientras permanezca activa."
            ),
            reply_markup=keyboard,
        )
        return

    # Compras no recurrentes: sendInvoice sí es correcto.
    await bot.send_invoice(
        chat_id=chat_id,
        title=product.title,
        description=product.description,
        payload=order.invoice_payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )


async def validate_pre_checkout(
    session: AsyncSession,
    query: PreCheckoutQuery,
) -> tuple[bool, str | None]:
    if query.currency != "XTR":
        return False, "Moneda de pago no válida."

    order = await find_order_by_payload(session, query.invoice_payload)
    if not order:
        return False, "La orden ya no existe."

    if order.stars_amount != query.total_amount:
        return False, "El importe no coincide con la orden."

    product = PRODUCTS.get(order.product_code)
    if not product or product.stars != query.total_amount:
        return False, "Producto o precio no válido."

    user = await session.get(User, order.user_id)
    if not user or user.telegram_id != query.from_user.id:
        return False, "Esta orden pertenece a otro usuario."

    return True, None


async def fulfill_successful_payment(
    session: AsyncSession,
    message: Message,
) -> str:
    payment = message.successful_payment
    if payment is None:
        raise ValueError("No successful_payment found")

    if await transaction_exists(
        session, payment.telegram_payment_charge_id
    ):
        return "Este pago ya había sido acreditado."

    order = await find_order_by_payload(session, payment.invoice_payload)
    if not order:
        raise ValueError("Order not found for successful payment")

    user = await session.get(User, order.user_id)
    if not user or user.telegram_id != message.from_user.id:
        raise ValueError("Payment user mismatch")

    if payment.currency != "XTR" or payment.total_amount != order.stars_amount:
        raise ValueError("Payment amount/currency mismatch")

    expiration = None
    if payment.subscription_expiration_date:
        expiration = datetime.fromtimestamp(
            payment.subscription_expiration_date,
            tz=timezone.utc,
        )

    tx = StarTransaction(
        order_id=order.id,
        user_id=user.id,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        stars_amount=payment.total_amount,
        is_recurring=bool(payment.is_recurring),
        subscription_expiration_date=expiration,
    )
    session.add(tx)

    now = datetime.now(timezone.utc)
    if order.product_code == "premium_monthly":
        user.premium_until = expiration or (now + timedelta(days=30))
        result_text = "👑 FreXo Premium quedó activado."
    elif order.product_code == "boost_30m":
        base = user.boost_until if user.boost_until and user.boost_until > now else now
        user.boost_until = base + timedelta(minutes=30)
        result_text = "🚀 Tu Boost quedó activado por 30 minutos."
    elif order.product_code == "super_interest":
        await add_consumable(session, user, "super_interest", 1)
        result_text = "💘 Recibiste 1 Super Interés."
    elif order.product_code == "reconnect":
        await add_consumable(session, user, "reconnect", 1)
        result_text = "↩️ Recibiste 1 intento de Reconexión."
    else:
        raise ValueError("Unknown product")

    await session.commit()
    return result_text
