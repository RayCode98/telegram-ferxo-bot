from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.keyboards import (
    explore_keyboard,
    main_menu,
    preferences_menu,
    profile_menu,
    store_keyboard,
)
from app.repositories import get_user_by_telegram
from app.services.conversation_ui import ensure_chat_panel
from app.services.growth import (
    active_travel_country,
    country_label,
    get_growth_profile,
    spotlight_active,
)
from app.services.matchmaking import get_active_partner
from app.services.profile import gender_label, send_profile_card


router = Router(name="navigation")


@router.callback_query(F.data == "nav:home")
async def nav_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()

    active = await get_active_partner(callback.from_user.id)
    if active:
        partner_tg, conversation_id = active
        async with SessionLocal() as session:
            viewer = await get_user_by_telegram(session, callback.from_user.id)
            partner = await get_user_by_telegram(session, partner_tg)
            if viewer and partner:
                await ensure_chat_panel(
                    callback.bot,
                    session,
                    viewer,
                    partner,
                    conversation_id,
                )

        await callback.answer("Tienes una conversación activa")
        await callback.message.answer(
            "💬 Tienes una conversación activa. "
            "Usa el panel fijado o los controles inferiores."
        )
        return

    await callback.answer()
    await callback.message.answer(
        "🏠 <b>Inicio</b>",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "nav:profile")
async def nav_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        await send_profile_card(
            callback.bot,
            callback.from_user.id,
            user,
            reply_markup=profile_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == "nav:prefs")
async def nav_prefs(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        await callback.message.answer(
            "⚙️ <b>Preferencias</b>\n\n"
            f"❤️ Buscar: {gender_label(user.seeking_gender)}\n"
            f"🎂 Edad: {user.min_age}–{user.max_age}\n"
            f"📍 Radio: {user.max_distance_km} km",
            reply_markup=preferences_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == "nav:explore")
async def nav_explore(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        growth = await get_growth_profile(session, user)
        travel = active_travel_country(growth)

        await callback.message.answer(
            "🌎 <b>Explorar</b>\n\n"
            f"🏠 País: <b>{country_label(growth.home_country_code)}</b>\n"
            f"🌎 Travel: <b>{country_label(travel) if travel else 'Inactivo'}</b>\n"
            f"🔥 Spotlight: <b>{'Activo' if spotlight_active(growth) else 'Inactivo'}</b>",
            reply_markup=explore_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "nav:store")
async def nav_store(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "⭐ <b>FreXo Store</b>",
        reply_markup=store_keyboard(),
    )
