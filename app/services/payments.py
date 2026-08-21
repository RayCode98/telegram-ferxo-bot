from __future__ import annotations

import uuid
from dataclasses import dataclass
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

from app.models import (
    Order,
    OrderContext,
    StarTransaction,
    User,
    VirtualGift,
)
from app.repositories import (
    add_consumable,
    find_order_by_payload,
    get_order_context,
    transaction_exists,
)
from app.services.analytics import track_event
from app.services.products import PRODUCTS


GIFT_LABELS = {
    "gift_rose": "🌹 Rosa",
    "gift_coffee": "☕ Café",
    "gift_flowers": "💐 Flores",
    "gift_diamond": "💎 Diamante",
}


@dataclass
class FulfillmentResult:
    text: str
    notify_telegram_id: int | None = None
    notify_text: str | None = None


async def create_order(
    session: AsyncSession,
    user: User,
    product_code: str,
    *,
    context_type: str | None = None,
    target_user_id: str | None = None,
    conversation_id: str | None = None,
    context_value: str | None = None,
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
    await session.flush()

    if context_type:
        session.add(
            OrderContext(
                order_id=order.id,
                context_type=context_type,
                target_user_id=target_user_id,
                conversation_id=conversation_id,
                context_value=context_value,
            )
        )

    await track_event(
        session,
        user,
        "invoice_created",
        {"product_code": product_code, "stars": product.stars},
    )
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
) -> FulfillmentResult:
    payment = message.successful_payment
    if payment is None:
        raise ValueError("No successful_payment found")

    if await transaction_exists(
        session, payment.telegram_payment_charge_id
    ):
        return FulfillmentResult("Este pago ya había sido acreditado.")

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

    session.add(
        StarTransaction(
            order_id=order.id,
            user_id=user.id,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            stars_amount=payment.total_amount,
            is_recurring=bool(payment.is_recurring),
            subscription_expiration_date=expiration,
        )
    )

    now = datetime.now(timezone.utc)
    result = FulfillmentResult("Compra acreditada.")

    if order.product_code == "premium_monthly":
        user.premium_until = expiration or (now + timedelta(days=30))
        result.text = "👑 FreXo Premium quedó activado."

    elif order.product_code == "boost_30m":
        base = user.boost_until if user.boost_until and user.boost_until > now else now
        user.boost_until = base + timedelta(minutes=30)
        result.text = "🚀 Tu Boost quedó activado por 30 minutos."

    elif order.product_code == "boost_60m":
        base = user.boost_until if user.boost_until and user.boost_until > now else now
        user.boost_until = base + timedelta(minutes=60)
        result.text = "🚀 Tu Boost quedó activado por 60 minutos."

    elif order.product_code == "super_interest":
        await add_consumable(session, user, "super_interest", 1)
        result.text = "💘 Recibiste 1 Super Interés."

    elif order.product_code == "reconnect":
        await add_consumable(session, user, "reconnect", 1)
        result.text = "↩️ Recibiste 1 intento de Reconexión."

    elif order.product_code == "travel_24h":
        await add_consumable(session, user, "travel_pass", 1)
        result.text = (
            "🌎 Recibiste 1 Travel Pass de 24 horas.\n"
            "Actívalo desde «🌎 Explorar» y elige el país."
        )

    elif order.product_code == "spotlight_3h":
        await add_consumable(session, user, "spotlight_3h", 1)
        result.text = (
            "🔥 Recibiste 1 Spotlight de 3 horas.\n"
            "Actívalo cuando quieras desde «🌎 Explorar»."
        )

    elif order.product_code in GIFT_LABELS:
        context = await get_order_context(session, order.id)
        if not context or not context.target_user_id:
            raise ValueError("Gift order has no target context")

        recipient = await session.get(User, context.target_user_id)
        if not recipient:
            raise ValueError("Gift recipient missing")

        session.add(
            VirtualGift(
                sender_id=user.id,
                recipient_id=recipient.id,
                conversation_id=context.conversation_id,
                gift_code=order.product_code,
                stars_amount=order.stars_amount,
            )
        )
        gift_label = GIFT_LABELS[order.product_code]
        result.text = f"🎁 Enviaste {gift_label} correctamente."
        result.notify_telegram_id = recipient.telegram_id
        result.notify_text = (
            "🤖 <b>FreXo</b>\n\n"
            f"🎁 <b>Tu conexión te envió {gift_label}.</b>\n"
            "El regalo queda guardado en tu perfil FreXo."
        )

    else:
        raise ValueError("Unknown product")

    await track_event(
        session,
        user,
        "purchase_success",
        {
            "product_code": order.product_code,
            "stars": order.stars_amount,
        },
    )
    await session.commit()
    return result
