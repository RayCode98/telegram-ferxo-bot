from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import or_, select
from app.database import SessionLocal
from app.keyboards import favorite_card_keyboard, favorites_keyboard, history_keyboard
from app.models import Conversation
from app.repositories import are_blocked, get_user_by_id, get_user_by_telegram
from app.services.matchmaking import age_of, get_active_partner
from app.services.profile import premium_active, send_profile_card
from app.services.social_graph import activity_label, favorite_users, remove_favorite

router=Router(name="history")
PAGE_SIZE=5

def reason_label(reason):
    return {"ended":"Terminada","next":"Siguiente","blocked":"Bloqueada","reported":"Reportada"}.get(reason,"Finalizada")

async def render_history(message: Message, telegram_id: int, page: int=0) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,telegram_id)
        if not user: return
        max_items=20 if premium_active(user) else 5
        offset=page*PAGE_SIZE
        if offset>=max_items:
            page=max(0,(max_items-1)//PAGE_SIZE); offset=page*PAGE_SIZE
        result=await session.execute(select(Conversation).where(or_(Conversation.user1_id==user.id,Conversation.user2_id==user.id)).order_by(Conversation.started_at.desc()).offset(offset).limit(PAGE_SIZE+1))
        rows=list(result.scalars()); visible=rows[:PAGE_SIZE]
        has_next=len(rows)>PAGE_SIZE and (offset+PAGE_SIZE)<max_items
        lines=["🕘 <b>Historial de conexiones</b>",""]
        if not visible: lines.append("Todavía no tienes conexiones en el historial.")
        for i,conversation in enumerate(visible,1):
            partner_id=conversation.user2_id if conversation.user1_id==user.id else conversation.user1_id
            partner=await get_user_by_id(session,partner_id)
            if not partner: continue
            age=age_of(partner.birth_date) or "?"; activity=await activity_label(session,partner); date=conversation.started_at.strftime('%d/%m/%Y')
            lines += [f"<b>{offset+i}. {partner.alias or 'Sin alias'}</b> · {age} años",f"   {activity}",f"   📅 {date} · {reason_label(conversation.ended_reason)}",""]
        if not premium_active(user): lines += ["👑 <b>Gratis:</b> últimas 5 conexiones.","Premium permite consultar las últimas 20."]
    await message.answer("\n".join(lines),reply_markup=history_keyboard(page,page>0,has_next))

@router.message(F.text == "🕘 Historial")
async def history_menu(message: Message) -> None:
    await render_history(message,message.from_user.id,0)

@router.callback_query(F.data.startswith("history:page:"))
async def history_page(callback: CallbackQuery) -> None:
    try: page=max(0,int(callback.data.rsplit(":",1)[1]))
    except ValueError: page=0
    await callback.answer(); await render_history(callback.message,callback.from_user.id,page)

@router.message(F.text == "⭐ Favoritos")
async def favorites_menu(message: Message) -> None:
    await render_favorites(message,message.from_user.id)

@router.callback_query(F.data == "favorites:refresh")
async def refresh_favorites(callback: CallbackQuery) -> None:
    await callback.answer(); await render_favorites(callback.message,callback.from_user.id)

async def render_favorites(message: Message, telegram_id: int) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,telegram_id)
        if not user: return
        favorites=await favorite_users(session,user,20)
        if not favorites:
            await message.answer("⭐ <b>Favoritos</b>\n\nTodavía no guardaste conexiones favoritas.",reply_markup=favorites_keyboard()); return
        await message.answer(f"⭐ <b>Favoritos</b>\n\nTienes {len(favorites)} guardados.",reply_markup=favorites_keyboard())
        for target in favorites:
            if target.is_banned or await are_blocked(session, user, target):
                continue
            await send_profile_card(message.bot,telegram_id,target,viewer=user,reply_markup=favorite_card_keyboard(target.id),session=session)

@router.callback_query(F.data.startswith("favorite:remove:"))
async def remove_favorite_callback(callback: CallbackQuery) -> None:
    target_id=callback.data.split(":",2)[2]
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        removed=await remove_favorite(session,user,target_id)
    await callback.answer("Favorito eliminado" if removed else "Ya no estaba en favoritos")
    try: await callback.message.delete()
    except Exception: pass



@router.callback_query(F.data.startswith("favorite:reconnect:"))
async def favorite_reconnect(callback: CallbackQuery) -> None:
    target_id = callback.data.split(":", 2)[2]

    if await get_active_partner(callback.from_user.id):
        await callback.answer(
            "Termina tu conversación actual antes de reconectar.",
            show_alert=True,
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        target = await get_user_by_id(session, target_id)

        if not user or not target:
            await callback.answer("Favorito no disponible.", show_alert=True)
            return

        conversation = await get_reconnectable_conversation_with_user(
            session,
            user,
            target,
        )
        if not conversation:
            await callback.answer(
                "No hay una conversación elegible para reconectar.",
                show_alert=True,
            )
            return

        if not await consume(session, user, "reconnect", 1):
            await callback.answer(
                "Necesitas un crédito de Reconexión.",
                show_alert=True,
            )
            await callback.message.answer(
                "↩️ Puedes comprar un intento de Reconexión por 15 ⭐.",
                reply_markup=store_keyboard(),
            )
            return

        request = await create_reconnect_request(
            session,
            conversation,
            user,
            target,
        )

    await callback.answer("Solicitud enviada ↩️")
    await callback.message.answer(
        "↩️ <b>Solicitud enviada a tu favorito.</b>\n\n"
        "La otra persona debe aceptar. El pago nunca obliga a reconectar."
    )

    await callback.bot.send_message(
        target.telegram_id,
        "↩️ <b>Una conexión guardada quiere volver a hablar contigo.</b>\n\n"
        "Puedes aceptar o rechazar sin revelar información adicional.",
        reply_markup=reconnect_request_keyboard(request.id),
    )
