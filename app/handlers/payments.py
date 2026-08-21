from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from app.config import settings
from app.database import SessionLocal
from app.keyboards import store_keyboard
from app.repositories import get_user_by_telegram
from app.services.payments import (
    create_order,
    fulfill_successful_payment,
    send_product_invoice,
    validate_pre_checkout,
)
from app.services.products import PRODUCTS


router = Router(name="payments")


@router.message(F.text == "👑 Premium")
async def premium_store(message: Message) -> None:
    await message.answer(
        "⭐ <b>FreXo Store</b>\n\n"
        "👑 <b>Premium</b>: filtros de edad/distancia, búsquedas ampliadas y prioridad.\n"
        "🚀 <b>Boost</b>: prioridad durante 30 minutos.\n"
        "💘 <b>Super Interés</b>: muestra un interés especial.\n"
        "↩️ <b>Reconectar</b>: crédito para recuperar una conexión elegible.\n\n"
        "Los productos digitales se pagan con Telegram Stars.",
        reply_markup=store_keyboard(),
    )


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
        order = await create_order(session, user, code)

    await callback.answer()
    await send_product_invoice(
        callback.bot,
        callback.from_user.id,
        order,
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    async with SessionLocal() as session:
        ok, error = await validate_pre_checkout(session, query)

    await query.answer(
        ok=ok,
        error_message=error,
    )


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    try:
        async with SessionLocal() as session:
            result = await fulfill_successful_payment(session, message)
        await message.answer(
            "✅ <b>Pago recibido correctamente.</b>\n\n" + result
        )
    except Exception:
        await message.answer(
            "⚠️ El pago fue recibido, pero ocurrió un problema al acreditar "
            "el beneficio. Usa /paysupport para que podamos revisarlo."
        )
        raise


@router.message(F.text == "/paysupport")
async def pay_support(message: Message) -> None:
    await message.answer(
        "💳 <b>Soporte de pagos</b>\n\n"
        "Si tuviste un problema con Stars o con un beneficio comprado, "
        f"contacta a {settings.support_username} e indica tu ID de Telegram: "
        f"<code>{message.from_user.id}</code>.\n\n"
        "No envíes contraseñas, códigos de acceso ni datos bancarios."
    )
