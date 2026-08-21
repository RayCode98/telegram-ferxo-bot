from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import (
    country_keyboard,
    explore_keyboard,
    main_menu,
    store_keyboard,
)
from app.repositories import consume, get_balance, get_user_by_telegram
from app.services.growth import (
    COUNTRIES,
    activate_reward_boost,
    activate_spotlight,
    activate_travel,
    active_travel_country,
    country_label,
    get_growth_profile,
    received_gift_count,
    referral_stats,
    set_home_country,
    spotlight_active,
)
from app.states import GrowthStates


router = Router(name="growth")


@router.message(F.text == "🌎 Explorar")
async def explore(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        growth = await get_growth_profile(session, user)
        travel_balance = await get_balance(session, user, "travel_pass")
        spotlight_balance = await get_balance(session, user, "spotlight_3h")
        boost_balance = await get_balance(session, user, "boost_30m_credit")

        travel_country = active_travel_country(growth)
        travel_status = (
            f"{country_label(travel_country)} hasta {growth.travel_until:%d/%m %H:%M}"
            if travel_country and growth.travel_until
            else "Inactivo"
        )
        spotlight_status = (
            f"Activo hasta {growth.spotlight_until:%d/%m %H:%M}"
            if spotlight_active(growth)
            else "Inactivo"
        )
        boost_status = (
            f"Activo hasta {user.boost_until:%d/%m %H:%M}"
            if user.boost_until and user.boost_until > datetime.now(timezone.utc)
            else "Inactivo"
        )

        await session.commit()

    await message.answer(
        "🌎 <b>Explorar y destacar</b>\n\n"
        f"🏠 País: <b>{country_label(growth.home_country_code)}</b>\n"
        f"🌎 Travel Mode: <b>{travel_status}</b>\n"
        f"🔥 Spotlight: <b>{spotlight_status}</b>\n"
        f"🚀 Boost: <b>{boost_status}</b>\n\n"
        f"🎟 Travel Pass disponibles: <b>{travel_balance}</b>\n"
        f"🔥 Spotlight disponibles: <b>{spotlight_balance}</b>\n"
        f"🚀 Boost gratis disponibles: <b>{boost_balance}</b>",
        reply_markup=explore_keyboard(),
    )


@router.callback_query(F.data == "growth:home_country")
async def choose_home_country(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "🏠 <b>¿Cuál es tu país?</b>\n\n"
        "Esto ayuda a Travel Mode y al matchmaking internacional.",
        reply_markup=country_keyboard("home"),
    )


@router.callback_query(F.data == "growth:travel_activate")
async def choose_travel_country(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        balance = await get_balance(session, user, "travel_pass")

    if balance < 1:
        await callback.answer("No tienes Travel Pass.", show_alert=True)
        await callback.message.answer(
            "🌎 Necesitas un Travel Pass para seleccionar otro país.",
            reply_markup=store_keyboard(),
        )
        return

    await callback.answer()
    await callback.message.answer(
        "🌎 <b>¿En qué país quieres conocer personas?</b>\n\n"
        "Al elegirlo se consumirá 1 Travel Pass y quedará activo 24 horas.",
        reply_markup=country_keyboard("travel"),
    )


@router.callback_query(F.data == "growth:spotlight_activate")
async def activate_spotlight_credit(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        if not await consume(session, user, "spotlight_3h", 1):
            await callback.answer("No tienes Spotlight disponible.", show_alert=True)
            await callback.message.answer(
                "🔥 Puedes comprar Spotlight en la tienda.",
                reply_markup=store_keyboard(),
            )
            return

        growth = await activate_spotlight(session, user)

    await callback.answer("Spotlight activado 🔥")
    await callback.message.answer(
        "🔥 <b>Spotlight activado.</b>\n\n"
        f"Tu perfil tendrá prioridad reforzada hasta "
        f"<b>{growth.spotlight_until:%d/%m %H:%M}</b>."
    )


@router.callback_query(F.data == "growth:boost_reward")
async def activate_boost_reward(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        if not await consume(session, user, "boost_30m_credit", 1):
            await callback.answer(
                "No tienes Boost gratis. Puedes conseguirlo con referidos.",
                show_alert=True,
            )
            return

        until = await activate_reward_boost(session, user)

    await callback.answer("Boost activado 🚀")
    await callback.message.answer(
        "🚀 <b>Boost de recompensa activado.</b>\n\n"
        f"Prioridad aumentada hasta <b>{until:%d/%m %H:%M}</b>."
    )


@router.callback_query(F.data == "growth:store")
async def growth_store(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "⭐ <b>FreXo Store</b>",
        reply_markup=store_keyboard(),
    )


@router.callback_query(F.data.startswith("country:"))
async def country_selected(callback: CallbackQuery, state: FSMContext) -> None:
    _, purpose, code = callback.data.split(":", 2)

    if code == "other":
        if purpose == "home":
            await state.set_state(GrowthStates.home_country)
        else:
            await state.set_state(GrowthStates.travel_country)

        await callback.answer()
        await callback.message.answer(
            "🌍 Escribe el código de dos letras de tu país.\n\n"
            "Ejemplos: <code>MX</code>, <code>CO</code>, <code>ES</code>, "
            "<code>US</code>."
        )
        return

    await _apply_country(callback, purpose, code)


async def _apply_country(
    callback: CallbackQuery,
    purpose: str,
    code: str,
) -> None:
    code = code.upper()

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        if purpose == "home":
            await set_home_country(session, user, code)
            await callback.answer("País actualizado")
            await callback.message.edit_text(
                f"✅ Tu país quedó configurado como "
                f"<b>{country_label(code)}</b>."
            )
            return

        if purpose == "travel":
            if not await consume(session, user, "travel_pass", 1):
                await callback.answer(
                    "Ya no tienes Travel Pass disponible.",
                    show_alert=True,
                )
                return

            growth = await activate_travel(session, user, code)
            await callback.answer("Travel Mode activado 🌎")
            await callback.message.edit_text(
                "🌎 <b>Travel Mode activado.</b>\n\n"
                f"Ahora buscarás personas de <b>{country_label(code)}</b> "
                f"hasta <b>{growth.travel_until:%d/%m %H:%M}</b>."
            )


async def _manual_country(
    message: Message,
    state: FSMContext,
    purpose: str,
) -> None:
    code = (message.text or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        await message.answer(
            "Escribe un código de país de 2 letras. Ejemplo: <code>MX</code>."
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        if purpose == "home":
            await set_home_country(session, user, code)
            await state.clear()
            await message.answer(
                f"✅ País configurado: <b>{country_label(code)}</b>.",
                reply_markup=main_menu(),
            )
            return

        if not await consume(session, user, "travel_pass", 1):
            await state.clear()
            await message.answer(
                "No tienes Travel Pass disponible.",
                reply_markup=store_keyboard(),
            )
            return

        growth = await activate_travel(session, user, code)
        await state.clear()
        await message.answer(
            f"🌎 Travel Mode activo para <b>{country_label(code)}</b> "
            f"hasta <b>{growth.travel_until:%d/%m %H:%M}</b>.",
            reply_markup=main_menu(),
        )


@router.message(GrowthStates.home_country)
async def manual_home_country(message: Message, state: FSMContext) -> None:
    await _manual_country(message, state, "home")


@router.message(GrowthStates.travel_country)
async def manual_travel_country(message: Message, state: FSMContext) -> None:
    await _manual_country(message, state, "travel")


@router.message(F.text == "🎁 Recompensas")
async def rewards(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        growth = await get_growth_profile(session, user)
        pending, qualified = await referral_stats(session, user)
        gifts = await received_gift_count(session, user)
        super_likes = await get_balance(session, user, "super_interest")
        travel_passes = await get_balance(session, user, "travel_pass")
        spotlights = await get_balance(session, user, "spotlight_3h")
        boost_credits = await get_balance(session, user, "boost_30m_credit")
        await session.commit()

    me = await message.bot.get_me()
    referral_link = (
        f"https://t.me/{me.username}?start=ref_{growth.referral_code}"
    )

    await message.answer(
        "🎁 <b>Recompensas y referidos</b>\n\n"
        f"✅ Referidos calificados: <b>{qualified}</b>\n"
        f"⏳ Pendientes: <b>{pending}</b>\n"
        f"🎁 Regalos recibidos: <b>{gifts}</b>\n\n"
        f"💘 Super Intereses: <b>{super_likes}</b>\n"
        f"🌎 Travel Pass: <b>{travel_passes}</b>\n"
        f"🔥 Spotlight: <b>{spotlights}</b>\n"
        f"🚀 Boost gratis: <b>{boost_credits}</b>\n\n"
        "<b>Premios:</b>\n"
        "• Cada referido calificado → 💘 1 Super Interés\n"
        "• 3 referidos → 🌎 Travel + 🔥 Spotlight\n"
        "• 5 referidos → 🚀 Boost + 💘 3 Super Intereses\n\n"
        "Un referido se califica cuando consigue su primer match.\n\n"
        f"🔗 <b>Tu enlace:</b>\n<code>{referral_link}</code>"
    )
