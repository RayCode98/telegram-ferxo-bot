from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.keyboards import weekly_missions_keyboard
from app.repositories import get_user_by_telegram
from app.services.weekly import (
    DAILY_GOAL,
    MATCH_GOAL,
    MESSAGE_GOAL,
    claim_weekly_reward,
    weekly_status,
)


router = Router(name="weekly")


async def render_weekly(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        status = await weekly_status(session, user)
        p = status.progress
        await session.commit()

    def check(done: bool) -> str:
        return "✅" if done else "▫️"

    text = (
        "🏆 <b>Misiones semanales</b>\n\n"
        f"{check(p.matches_count >= MATCH_GOAL)} "
        f"Consigue {MATCH_GOAL} matches: "
        f"<b>{min(p.matches_count, MATCH_GOAL)}/{MATCH_GOAL}</b>\n"
        "   🎁 Premio: 💘 2 Super Intereses\n\n"
        f"{check(p.messages_count >= MESSAGE_GOAL)} "
        f"Envía {MESSAGE_GOAL} mensajes: "
        f"<b>{min(p.messages_count, MESSAGE_GOAL)}/{MESSAGE_GOAL}</b>\n"
        "   🎁 Premio: 🚀 Boost 30 min\n\n"
        f"{check(p.daily_claims_count >= DAILY_GOAL)} "
        f"Reclama recompensa diaria {DAILY_GOAL} veces: "
        f"<b>{min(p.daily_claims_count, DAILY_GOAL)}/{DAILY_GOAL}</b>\n"
        "   🎁 Premio: 🌎 Travel Pass\n\n"
        "🏆 Reclama las 3 misiones para desbloquear:\n"
        "   🔥 Spotlight de 3 horas\n\n"
        f"📅 Semana: <code>{p.week_key}</code>"
    )

    await callback.message.answer(
        text,
        reply_markup=weekly_missions_keyboard(
            status.matches_ready,
            status.messages_ready,
            status.daily_ready,
            status.bonus_ready,
        ),
    )


@router.callback_query(F.data == "weekly:open")
async def weekly_open(callback: CallbackQuery) -> None:
    await callback.answer()
    await render_weekly(callback)


@router.callback_query(F.data.startswith("weekly:claim:"))
async def weekly_claim(callback: CallbackQuery) -> None:
    mission = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        ok, result = await claim_weekly_reward(
            session,
            user,
            mission,
        )

    if not ok:
        await callback.answer(result, show_alert=True)
        return

    await callback.answer("Premio reclamado 🎁")
    await callback.message.answer(
        "🎁 <b>Misión completada.</b>\n\n"
        f"Recibiste: <b>{result}</b>"
    )
    await render_weekly(callback)
