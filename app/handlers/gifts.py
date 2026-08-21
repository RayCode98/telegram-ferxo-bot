from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.keyboards import gift_keyboard
from app.repositories import get_user_by_telegram
from app.services.matchmaking import get_active_partner
from app.services.payments import create_order, send_product_invoice
from app.services.products import PRODUCTS


router = Router(name="gifts")


@router.callback_query(F.data == "chat:gift")
async def gift_menu(callback: CallbackQuery) -> None:
    if not await get_active_partner(callback.from_user.id):
        await callback.answer("No hay conversación activa.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "🎁 <b>Envía un regalo virtual</b>\n\n"
        "El regalo no revela tu Telegram ni obliga a la otra persona "
        "a compartir información.",
        reply_markup=gift_keyboard(),
    )


@router.callback_query(F.data.startswith("gift:"))
async def buy_gift(callback: CallbackQuery) -> None:
    product_code = callback.data.split(":", 1)[1]
    if product_code not in PRODUCTS or not product_code.startswith("gift_"):
        await callback.answer("Regalo no disponible.", show_alert=True)
        return

    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("La conversación ya terminó.", show_alert=True)
        return

    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        sender = await get_user_by_telegram(session, callback.from_user.id)
        recipient = await get_user_by_telegram(session, partner_tg)
        if not sender or not recipient:
            await callback.answer("No se pudo preparar el regalo.", show_alert=True)
            return

        order = await create_order(
            session,
            sender,
            product_code,
            context_type="gift",
            target_user_id=recipient.id,
            conversation_id=conversation_id,
        )

    await callback.answer()
    await send_product_invoice(
        callback.bot,
        callback.from_user.id,
        order,
    )
