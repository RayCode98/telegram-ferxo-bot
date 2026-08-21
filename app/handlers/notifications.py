from aiogram import F, Router
from aiogram.types import CallbackQuery
from app.database import SessionLocal
from app.handlers.matchmaking import begin_search
from app.repositories import get_user_by_telegram
from app.services.social_graph import get_experience_preferences, toggle_smart_notifications

router=Router(name="notifications")

@router.callback_query(F.data == "smart:search")
async def smart_search(callback: CallbackQuery) -> None:
    await callback.answer("Buscando…")
    await begin_search(callback.message, "global", callback.from_user.id)

@router.callback_query(F.data == "smart:disable")
async def smart_disable(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        prefs=await get_experience_preferences(session,user)
        if prefs.smart_notifications: await toggle_smart_notifications(session,user)
    await callback.answer("Avisos desactivados")
    await callback.message.edit_text("🔕 Avisos de compatibilidad desactivados.\n\nPuedes volver a activarlos desde ⚙️ Preferencias.")
