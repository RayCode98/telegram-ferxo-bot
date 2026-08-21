from __future__ import annotations
from datetime import datetime, timezone
from aiogram import Bot, F, Router
from aiogram.types import BotSubscriptionUpdated, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, PreCheckoutQuery
from app.config import settings
from app.database import SessionLocal
from app.keyboards import store_keyboard
from app.repositories import get_user_by_telegram
from app.services.payments import create_order, fulfill_successful_payment, send_product_invoice, validate_pre_checkout
from app.services.products import PRODUCTS
from app.services.subscriptions import apply_subscription_update, get_subscription_state
router=Router(name="payments")

def premium_manage_keyboard(auto_renew_enabled: bool) -> InlineKeyboardMarkup:
    rows=[[InlineKeyboardButton(text="⏹ Cancelar renovación" if auto_renew_enabled else "▶️ Reactivar renovación",callback_data="premium:cancel_renewal" if auto_renew_enabled else "premium:resume_renewal")],[InlineKeyboardButton(text="⭐ Ver tienda",callback_data="premium:store")],[InlineKeyboardButton(text="🏠 Inicio",callback_data="nav:home")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == "👑 Premium")
async def premium_store(message: Message) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,message.from_user.id); state=await get_subscription_state(session,user) if user else None
    now=datetime.now(timezone.utc)
    if user and user.premium_until and user.premium_until>now:
        renew=state.auto_renew_enabled if state else True
        await message.answer("👑 <b>FreXo Premium</b>\n\nEstado: <b>✅ Activo</b>\nVigente hasta: <b>"+user.premium_until.strftime("%d/%m/%Y %H:%M UTC")+"</b>\nRenovación automática: <b>"+("Sí" if renew else "No")+"</b>",reply_markup=premium_manage_keyboard(renew)); return
    await message.answer("⭐ <b>FreXo Store</b>\n\n👑 Premium: filtros avanzados, perfiles ampliados y prioridad.\n🚀 Boost: prioridad temporal.\n🌎 Travel: busca en un país concreto.\n🔥 Spotlight: mayor visibilidad.\n💘 Super Interés y ↩️ Reconectar: consumibles sociales.\n\nLos productos digitales se pagan con Telegram Stars.",reply_markup=store_keyboard())

@router.callback_query(F.data == "premium:store")
async def open_store(callback: CallbackQuery) -> None:
    await callback.answer(); await callback.message.answer("⭐ <b>FreXo Store</b>",reply_markup=store_keyboard())

async def _set_renewal(callback: CallbackQuery,canceled: bool) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        state=await get_subscription_state(session,user)
        if not state or not state.telegram_payment_charge_id:
            await callback.answer("No encontramos una suscripción administrable.",show_alert=True); return
        charge=state.telegram_payment_charge_id
    await callback.bot.edit_user_star_subscription(user_id=callback.from_user.id,telegram_payment_charge_id=charge,is_canceled=canceled)
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id); state=await get_subscription_state(session,user)
        if state: state.auto_renew_enabled=not canceled; state.state="canceled" if canceled else "active"; await session.commit()
    await callback.answer("Renovación actualizada"); await callback.message.answer("✅ La renovación automática quedó "+("cancelada." if canceled else "reactivada.")+"\n\nTu Premium actual sigue vigente hasta su fecha de expiración.")

@router.callback_query(F.data == "premium:cancel_renewal")
async def cancel(callback: CallbackQuery) -> None: await _set_renewal(callback,True)
@router.callback_query(F.data == "premium:resume_renewal")
async def resume(callback: CallbackQuery) -> None: await _set_renewal(callback,False)

@router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery) -> None:
    code=callback.data.split(":",1)[1]
    if code not in PRODUCTS: await callback.answer("Producto no disponible.",show_alert=True); return
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: await callback.answer("Usa /start primero.",show_alert=True); return
        order=await create_order(session,user,code)
    await callback.answer(); await send_product_invoice(callback.bot,callback.from_user.id,order)

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    async with SessionLocal() as session: ok,error=await validate_pre_checkout(session,query)
    await query.answer(ok=ok,error_message=error)

@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    try:
        async with SessionLocal() as session: result=await fulfill_successful_payment(session,message)
        await message.answer("✅ <b>Pago recibido correctamente.</b>\n\n"+result.text)
        if result.notify_telegram_id and result.notify_text: await message.bot.send_message(result.notify_telegram_id,result.notify_text)
    except Exception:
        await message.answer("⚠️ El pago fue recibido, pero ocurrió un problema al acreditar el beneficio. Usa /paysupport para que podamos revisarlo."); raise

@router.subscription()
async def subscription_updated(event: BotSubscriptionUpdated, bot: Bot) -> None:
    async with SessionLocal() as session: user,state=await apply_subscription_update(session,event)
    if not user or not state: return
    text={"canceled":"👑 <b>Renovación de Premium cancelada.</b>\n\nTu acceso actual permanece activo hasta su fecha de expiración.","active":"👑 <b>Renovación de Premium reactivada.</b>","failed":"⚠️ <b>No se pudo renovar FreXo Premium.</b>\n\nRevisa tu saldo de Telegram Stars si deseas continuar con la suscripción."}.get(event.state,f"👑 Estado de suscripción actualizado: {event.state}")
    try: await bot.send_message(user.telegram_id,text)
    except Exception: pass

@router.message(F.text == "/paysupport")
async def pay_support(message: Message) -> None:
    await message.answer("💳 <b>Soporte de pagos</b>\n\nSi tuviste un problema con Stars o con un beneficio comprado, contacta a "+settings.support_username+f" e indica tu ID de Telegram: <code>{message.from_user.id}</code>.\n\nNo envíes contraseñas, códigos de acceso ni datos bancarios.")
