from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.models import Conversation
from app.repositories import get_user_by_telegram
from app.services.quality import save_feedback


router = Router(name="feedback")


@router.callback_query(F.data.startswith("feedback:"))
async def conversation_feedback(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return

    rating = parts[1]
    conversation_id = parts[2]

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        conversation = await session.get(Conversation, conversation_id)

        if not user or not conversation:
            await callback.answer(
                "Esta conversación ya no está disponible.",
                show_alert=True,
            )
            return

        if user.id not in {conversation.user1_id, conversation.user2_id}:
            await callback.answer("No autorizado.", show_alert=True)
            return

        saved = await save_feedback(
            session,
            conversation,
            user,
            rating,
        )

    if not saved:
        await callback.answer("Ya habías valorado esta conversación.")
        return

    label = {
        "good": "👍 Buena",
        "neutral": "😐 Normal",
        "bad": "👎 Mala",
    }.get(rating, "Guardada")

    await callback.answer("Gracias por tu opinión")
    await callback.message.edit_text(
        f"✅ Valoración guardada: <b>{label}</b>.\n\n"
        "Gracias por ayudar a mejorar FreXo."
    )
