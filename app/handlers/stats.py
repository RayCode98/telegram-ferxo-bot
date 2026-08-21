from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, or_, select

from app.database import SessionLocal
from app.models import (
    Conversation,
    ConversationQuality,
    Favorite,
    Interest,
    RetentionProfile,
    VirtualGift,
)
from app.repositories import get_user_by_telegram


router = Router(name="personal_stats")


@router.callback_query(F.data == "profile:stats")
async def personal_stats(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        conversations = (
            await session.execute(
                select(func.count(Conversation.id)).where(
                    or_(
                        Conversation.user1_id == user.id,
                        Conversation.user2_id == user.id,
                    )
                )
            )
        ).scalar_one()

        likes_given = (
            await session.execute(
                select(func.count(Interest.id)).where(
                    Interest.from_user_id == user.id
                )
            )
        ).scalar_one()

        likes_received = (
            await session.execute(
                select(func.count(Interest.id)).where(
                    Interest.to_user_id == user.id
                )
            )
        ).scalar_one()

        favorites = (
            await session.execute(
                select(func.count(Favorite.id)).where(
                    Favorite.user_id == user.id
                )
            )
        ).scalar_one()

        gifts = (
            await session.execute(
                select(func.count(VirtualGift.id)).where(
                    VirtualGift.recipient_id == user.id
                )
            )
        ).scalar_one()

        # Mensajes contabilizados desde v1.8.
        q_rows = await session.execute(
            select(ConversationQuality, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationQuality.conversation_id,
            )
            .where(
                or_(
                    Conversation.user1_id == user.id,
                    Conversation.user2_id == user.id,
                )
            )
        )
        messages = 0
        for quality, conversation in q_rows.all():
            if conversation.user1_id == user.id:
                messages += quality.user1_messages
            else:
                messages += quality.user2_messages

        retention = (
            await session.execute(
                select(RetentionProfile).where(
                    RetentionProfile.user_id == user.id
                )
            )
        ).scalar_one_or_none()

        streak = retention.streak_count if retention else 0
        longest = retention.longest_streak if retention else 0

    await callback.answer()
    await callback.message.answer(
        "📊 <b>Mis estadísticas FreXo</b>\n\n"
        f"🤝 Conexiones: <b>{conversations}</b>\n"
        f"💬 Mensajes desde v1.8: <b>{messages}</b>\n"
        f"❤️ Intereses enviados: <b>{likes_given}</b>\n"
        f"💘 Intereses recibidos: <b>{likes_received}</b>\n"
        f"⭐ Favoritos guardados: <b>{favorites}</b>\n"
        f"🎁 Regalos recibidos: <b>{gifts}</b>\n"
        f"🔥 Racha actual: <b>{streak}</b>\n"
        f"🏆 Mejor racha: <b>{longest}</b>"
    )
