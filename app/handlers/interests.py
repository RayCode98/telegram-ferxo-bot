from aiogram import F, Router
from aiogram.types import CallbackQuery
from app.database import SessionLocal
from app.keyboards import interests_keyboard
from app.repositories import get_user_by_telegram
from app.services.social_graph import interest_codes, interest_labels, toggle_interest

router=Router(name="interests")

@router.callback_query(F.data == "profile:interests")
async def open_interests(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        selected=await interest_codes(session,user)
    await callback.answer()
    await callback.message.answer("🎯 <b>Mis intereses</b>\n\nElige hasta 6. FreXo los usa para mejorar compatibilidad y proponer temas en común.", reply_markup=interests_keyboard(selected))

@router.callback_query(F.data.startswith("interest:toggle:"))
async def toggle_interest_callback(callback: CallbackQuery) -> None:
    code=callback.data.split(":",2)[2]
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        selected,error=await toggle_interest(session,user,code)
    if error:
        await callback.answer(error,show_alert=True); return
    await callback.answer("Intereses actualizados")
    await callback.message.edit_reply_markup(reply_markup=interests_keyboard(selected))

@router.callback_query(F.data == "interest:done")
async def finish_interests(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        labels=interest_labels(await interest_codes(session,user))
    await callback.answer()
    await callback.message.edit_text("✅ <b>Intereses guardados.</b>\n\n" + (" · ".join(labels) if labels else "Todavía no seleccionaste intereses."))
