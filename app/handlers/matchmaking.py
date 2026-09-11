from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import active_chat_keyboard, search_cancel_keyboard, premium_offer_keyboard
from app.repositories import get_user_by_telegram
from app.services.matchmaking import (
    can_search,
    dequeue,
    get_active_partner,
    try_match,
)
from app.services.profile import send_profile_card
from app.services.conversation_ui import refresh_pair_panels, send_match_ready_notice
from app.services.notifications import notify_compatible_users
from app.services.security import get_active_restriction, restriction_text, search_allowed
from app.services.analytics import track_event
from app.services.monetization import record_paywall_view, render_premium_offer


router = Router(name="matchmaking")


async def begin_search(message: Message, mode: str, user_telegram_id: int | None = None) -> None:
    telegram_id = user_telegram_id or message.from_user.id
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, telegram_id)
        if not user or not user.onboarding_completed:
            await message.answer("Primero usa /start para completar tu perfil.")
            return
        restriction = await get_active_restriction(session, user)
        if restriction:
            await message.answer(restriction_text(restriction))
            return

        burst_ok, burst_ttl = await search_allowed(user.telegram_id)
        if not burst_ok:
            await message.answer(
                f"⏳ Estás buscando demasiado rápido. Intenta de nuevo en "
                f"aproximadamente {burst_ttl} segundos."
            )
            return
        if await get_active_partner(user.telegram_id):
            await message.answer("Ya tienes una conversación activa.")
            return

        if mode == "nearby" and (
            user.latitude is None or user.longitude is None
        ):
            await message.answer(
                "📍 Para buscar cerca de ti primero comparte tu ubicación "
                "desde <b>⚙️ Preferencias</b>."
            )
            return

        allowed, remaining = await can_search(user)
        if not allowed:
            await record_paywall_view(session, user, "search_limit")
            await session.commit()
            await message.answer(
                render_premium_offer("search_limit"),
                reply_markup=premium_offer_keyboard("search_limit"),
            )
            return

        await track_event(
            session,
            user,
            "search_started",
            {"mode": mode},
        )
        # Se confirma antes de intentar el match para que también cuenten
        # búsquedas que terminan esperando en la cola.
        await session.commit()

        result = await try_match(session, user, mode)
        if not result:
            extra = (
                f"\n\nTe quedan aproximadamente {remaining} búsquedas gratuitas hoy."
                if remaining
                else ""
            )
            await message.answer(
                "🔎 <b>Buscando una persona compatible…</b>\n"
                "Te avisaré cuando aparezca alguien."
                + extra,
                reply_markup=search_cancel_keyboard(),
            )
            await notify_compatible_users(message.bot, session, user, mode=mode, limit=3)
            return

        partner, _conversation_id = result

        # Primero creamos/fijamos el panel de conversación para ambos.
        await refresh_pair_panels(
            message.bot,
            session,
            user,
            partner,
            _conversation_id,
        )

        # Después mostramos la tarjeta de la conexión.
        await send_profile_card(
            message.bot,
            telegram_id,
            partner,
            viewer=user,
            reply_markup=active_chat_keyboard(),
            session=session,
        )
        await send_profile_card(
            message.bot,
            partner.telegram_id,
            user,
            viewer=partner,
            reply_markup=active_chat_keyboard(),
            session=session,
        )

        # Este aviso queda como el mensaje más reciente y deja claro que el
        # match YA ocurrió y que sólo tienen que comenzar a escribir.
        await send_match_ready_notice(
            message.bot,
            session,
            user,
            partner,
        )
        await send_match_ready_notice(
            message.bot,
            session,
            partner,
            user,
        )


@router.message(F.text == "🎲 Buscar persona")
async def search_global(message: Message) -> None:
    await begin_search(message, "global")


@router.message(F.text == "📍 Personas cerca")
async def search_nearby(message: Message) -> None:
    await begin_search(message, "nearby")


@router.callback_query(F.data == "search:cancel")
async def cancel_search(callback: CallbackQuery) -> None:
    await dequeue(callback.from_user.id)
    await callback.answer("Búsqueda cancelada")
    await callback.message.edit_text("❌ Búsqueda cancelada.")
