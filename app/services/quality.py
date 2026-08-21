from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal
from app.models import (
    Conversation,
    ConversationFeedback,
    ConversationQuality,
    User,
)
from app.redis_client import redis
from app.repositories import end_conversation, get_user_by_id
from app.services.analytics import track_event
from app.services.social_graph import common_interests, interest_labels
from app.services.weekly import record_weekly_event


GENERIC_SUGGESTIONS = [
    "¿Qué lugar te gustaría conocer algún día? ✈️",
    "¿Qué canción no te cansas de escuchar? 🎵",
    "¿Qué plan disfrutas más un fin de semana? 😄",
    "¿Qué película o serie recomendarías ahora mismo? 🎬",
    "¿Prefieres playa, montaña o ciudad? 🌊⛰️🏙️",
    "¿Qué comida podrías repetir toda la semana? 🍕",
    "¿Qué habilidad te gustaría aprender este año? ✨",
]

INTEREST_QUESTIONS = {
    "music": [
        "¿Qué artista estás escuchando mucho últimamente? 🎵",
        "¿Qué canción pondrías para animar una reunión? 🎶",
    ],
    "travel": [
        "¿Cuál ha sido tu viaje favorito hasta ahora? ✈️",
        "Si mañana pudieras viajar gratis, ¿a dónde irías? 🌎",
    ],
    "gaming": [
        "¿Qué videojuego te ha atrapado últimamente? 🎮",
        "¿Prefieres jugar competitivo o relajarte con un buen juego? 🕹️",
    ],
    "sports": [
        "¿Qué deporte disfrutas más ver o practicar? ⚽",
        "¿Tienes algún equipo o atleta favorito? 🏆",
    ],
    "movies": [
        "¿Qué película o serie recomendarías sin pensarlo? 🎬",
        "¿Qué género de películas disfrutas más? 🍿",
    ],
    "reading": [
        "¿Qué libro te ha gustado mucho recientemente? 📚",
        "¿Qué tipo de historias disfrutas leer? 📖",
    ],
    "fitness": [
        "¿Qué tipo de entrenamiento disfrutas más? 🏋️",
        "¿Tienes alguna meta fitness para este año? 💪",
    ],
    "food": [
        "¿Cuál es tu comida favorita? 🍕",
        "¿Prefieres cocinar o descubrir lugares para comer? 🍽️",
    ],
    "nature": [
        "¿Prefieres playa, bosque o montaña? 🌿",
        "¿Cuál es tu plan favorito al aire libre? 🌄",
    ],
    "tech": [
        "¿Qué tecnología te parece más interesante ahora mismo? 💻",
        "¿Eres de probar gadgets nuevos o esperar a que maduren? 📱",
    ],
    "pets": [
        "¿Tienes mascotas? 🐾",
        "¿Perros, gatos o algún animal menos común? 😄",
    ],
    "art": [
        "¿Qué tipo de arte disfrutas más? 🎨",
        "¿Hay algún artista que te guste mucho? 🖼️",
    ],
    "dance": [
        "¿Qué música te hace querer bailar de inmediato? 💃",
        "¿Bailas por diversión o has tomado clases? 🕺",
    ],
    "photography": [
        "¿Qué disfrutas más fotografiar? 📸",
        "¿Prefieres fotos espontáneas o planeadas? 📷",
    ],
    "business": [
        "¿Qué tipo de proyecto te gustaría emprender algún día? 💼",
        "¿Qué negocio te parece interesante actualmente? 📈",
    ],
    "languages": [
        "¿Qué idioma te gustaría aprender? 🌐",
        "¿Has aprendido alguna frase curiosa en otro idioma? 🗣️",
    ],
}


async def get_quality(
    session: AsyncSession,
    conversation: Conversation,
) -> ConversationQuality:
    result = await session.execute(
        select(ConversationQuality).where(
            ConversationQuality.conversation_id == conversation.id
        )
    )
    quality = result.scalar_one_or_none()
    if quality:
        return quality

    quality = ConversationQuality(conversation_id=conversation.id)
    session.add(quality)
    await session.flush()
    return quality


async def record_relayed_message(
    session: AsyncSession,
    conversation: Conversation,
    sender: User,
) -> bool:
    """
    Registra mensajes para calidad. Devuelve True cuando conviene mostrar
    un recordatorio suave por demasiados mensajes consecutivos sin respuesta.
    """
    quality = await get_quality(session, conversation)
    now = datetime.now(timezone.utc)

    if sender.id == conversation.user1_id:
        quality.user1_messages += 1
    elif sender.id == conversation.user2_id:
        quality.user2_messages += 1

    if quality.last_sender_id == sender.id:
        quality.consecutive_sender_messages += 1
    else:
        quality.last_sender_id = sender.id
        quality.consecutive_sender_messages = 1

    quality.last_message_at = now
    quality.nudge_sent_at = None

    await record_weekly_event(
        session,
        sender,
        "message",
        amount=1,
    )
    await track_event(
        session,
        sender,
        "chat_message_relayed",
        {"conversation_id": conversation.id},
    )
    await session.commit()

    if (
        quality.consecutive_sender_messages
        >= settings.consecutive_message_nudge
    ):
        key = f"quality:consecutive:{conversation.id}:{sender.id}"
        first = await redis.set(key, "1", ex=900, nx=True)
        return bool(first)

    return False


async def suggestion_for_pair(
    session: AsyncSession,
    user: User,
    partner: User,
) -> str:
    common = await common_interests(session, user, partner)

    if common:
        code = random.choice(list(common))
        questions = INTEREST_QUESTIONS.get(code)
        if questions:
            return random.choice(questions)

    return random.choice(GENERIC_SUGGESTIONS)


async def save_feedback(
    session: AsyncSession,
    conversation: Conversation,
    user: User,
    rating: str,
) -> bool:
    if rating not in {"good", "neutral", "bad"}:
        return False

    existing = await session.execute(
        select(ConversationFeedback).where(
            ConversationFeedback.conversation_id == conversation.id,
            ConversationFeedback.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        return False

    session.add(
        ConversationFeedback(
            conversation_id=conversation.id,
            user_id=user.id,
            rating=rating,
        )
    )
    await track_event(
        session,
        user,
        "conversation_feedback",
        {
            "conversation_id": conversation.id,
            "rating": rating,
        },
    )
    await session.commit()
    return True


async def quality_monitor_iteration(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    nudge_cutoff = now - timedelta(minutes=settings.ghosting_nudge_minutes)
    close_cutoff = now - timedelta(hours=settings.conversation_idle_close_hours)

    async with SessionLocal() as session:
        # Conversaciones con al menos un mensaje.
        result = await session.execute(
            select(ConversationQuality, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationQuality.conversation_id,
            )
            .where(
                Conversation.status == "active",
                ConversationQuality.last_message_at.is_not(None),
                ConversationQuality.last_message_at <= nudge_cutoff,
            )
            .limit(100)
        )
        rows = list(result.all())

        for quality, conversation in rows:
            # Cierre por abandono prolongado.
            if quality.last_message_at and quality.last_message_at <= close_cutoff:
                user1 = await get_user_by_id(session, conversation.user1_id)
                user2 = await get_user_by_id(session, conversation.user2_id)
                await end_conversation(
                    session,
                    conversation.id,
                    None,
                    "idle_timeout",
                )

                from app.services.matchmaking import clear_active_pair
                from app.services.conversation_ui import close_chat_panel

                if user1 and user2:
                    await clear_active_pair(
                        user1.telegram_id,
                        user2.telegram_id,
                    )
                    await close_chat_panel(
                        bot,
                        user1.telegram_id,
                        reason="Conversación cerrada por inactividad.",
                        notice=(
                            "⌛ <b>Esta conversación se cerró por inactividad.</b>\n\n"
                            "Puedes iniciar una nueva búsqueda cuando quieras."
                        ),
                        conversation_id=conversation.id,
                        ask_feedback=True,
                    )
                    await close_chat_panel(
                        bot,
                        user2.telegram_id,
                        reason="Conversación cerrada por inactividad.",
                        notice=(
                            "⌛ <b>Esta conversación se cerró por inactividad.</b>\n\n"
                            "Puedes iniciar una nueva búsqueda cuando quieras."
                        ),
                        conversation_id=conversation.id,
                        ask_feedback=True,
                    )
                continue

            # Sólo un recordatorio por cada tramo de inactividad.
            if quality.nudge_sent_at is not None:
                continue

            if not quality.last_sender_id:
                continue

            last_sender = await get_user_by_id(session, quality.last_sender_id)
            if not last_sender:
                continue

            try:
                await bot.send_message(
                    last_sender.telegram_id,
                    "🤖 <b>FreXo</b>\n\n"
                    "⏳ Tu conexión aún no ha respondido.\n\n"
                    "Dale un poco de tiempo y evita enviar muchos mensajes seguidos. "
                    "Puedes seguir esperando o usar «🔄 Siguiente» cuando quieras."
                )
            except Exception:
                pass

            quality.nudge_sent_at = now

        await session.commit()


async def conversation_quality_monitor(bot: Bot) -> None:
    import asyncio

    while True:
        try:
            await quality_monitor_iteration(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            # El monitor nunca debe detener el bot principal.
            pass

        await asyncio.sleep(300)
