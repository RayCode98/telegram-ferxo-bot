from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from app.database import SessionLocal
from app.keyboards import (
    adult_keyboard,
    gender_keyboard,
    location_keyboard,
    main_menu,
    onboarding_country_keyboard,
    interests_keyboard,
)
from app.repositories import get_or_create_user, get_user_by_telegram
from app.states import Onboarding
from app.services.security import get_active_restriction, restriction_text
from app.services.lifecycle import get_lifecycle
from app.services.growth import get_growth_profile, register_referral, set_home_country, country_label


router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.language_code,
        )

        await get_growth_profile(session, user)

        lifecycle = await get_lifecycle(session, user)
        if lifecycle.state == "deleted":
            await session.commit()
            await message.answer(
                "🗑 <b>Tu cuenta FreXo está eliminada.</b>\n\n"
                "Si quieres volver, puedes reactivarla y completar el registro otra vez.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="♻️ Reactivar cuenta", callback_data="account:reactivate"
                )]]),
            )
            return

        parts = (message.text or "").split(maxsplit=1)
        start_parameter = parts[1] if len(parts) > 1 else None
        if (
            start_parameter
            and start_parameter.startswith("ref_")
            and not user.onboarding_completed
        ):
            await register_referral(
                session,
                user,
                start_parameter[4:],
            )

    async with SessionLocal() as session:
        current_user = await get_user_by_telegram(session, message.from_user.id)
        restriction = (
            await get_active_restriction(session, current_user)
            if current_user
            else None
        )

    if restriction:
        await message.answer(restriction_text(restriction))
        return

    if user.onboarding_completed:
        await message.answer(
            "👋 <b>Bienvenido de nuevo a FreXo.</b>\n\n"
            "Conoce personas sin revelar tu Telegram hasta que tú quieras.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        "🔞 <b>FreXo es exclusivamente para mayores de 18 años.</b>\n\n"
        "Al continuar confirmas que tienes al menos 18 años. "
        "Nunca compartiremos tu ubicación exacta con otros usuarios.",
        reply_markup=adult_keyboard(),
    )


@router.callback_query(F.data == "adult:no")
async def adult_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "FreXo sólo está disponible para personas mayores de 18 años."
    )


@router.callback_query(F.data == "adult:yes")
async def adult_yes(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        user.adult_confirmed = True
        await session.commit()

    await callback.answer()
    await state.set_state(Onboarding.alias)
    await callback.message.edit_text(
        "👤 <b>¿Cómo quieres que te llamen dentro de FreXo?</b>\n\n"
        "Usa un alias. No tiene que coincidir con tu nombre de Telegram."
    )


@router.message(Onboarding.alias)
async def onboarding_alias(message: Message, state: FSMContext) -> None:
    alias = (message.text or "").strip()
    if not 2 <= len(alias) <= 40:
        await message.answer("El alias debe tener entre 2 y 40 caracteres.")
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        user.alias = alias
        await session.commit()

    await state.set_state(Onboarding.birth_date)
    await message.answer(
        "🎂 Escribe tu fecha de nacimiento en formato <b>DD/MM/AAAA</b>.\n\n"
        "La usamos para aplicar filtros de edad; no se mostrará completa."
    )


@router.message(Onboarding.birth_date)
async def onboarding_birth_date(message: Message, state: FSMContext) -> None:
    try:
        birth = datetime.strptime((message.text or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        await message.answer("Formato inválido. Ejemplo: <b>25/08/1999</b>")
        return

    today = datetime.now(timezone.utc).date()
    age = today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )
    if age < 18 or age > 100:
        await message.answer(
            "No podemos continuar con esa fecha. FreXo es sólo para mayores de 18 años."
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        user.birth_date = birth
        await session.commit()

    await state.set_state(Onboarding.gender)
    await message.answer(
        "🚻 <b>¿Cómo quieres aparecer en FreXo?</b>",
        reply_markup=gender_keyboard("gender"),
    )


@router.callback_query(Onboarding.gender, F.data.startswith("gender:"))
async def onboarding_gender(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "any":
        await callback.answer("Elige cómo te identificas dentro del perfil.")
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        user.gender = value
        await session.commit()

    await callback.answer()
    await state.set_state(Onboarding.seeking_gender)
    await callback.message.edit_text(
        "❤️ <b>¿A quién quieres conocer?</b>",
        reply_markup=gender_keyboard("seeking"),
    )


@router.callback_query(
    Onboarding.seeking_gender,
    F.data.startswith("seeking:"),
)
async def onboarding_seeking(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        user.seeking_gender = value
        await session.commit()

    await callback.answer()
    await state.set_state(Onboarding.country)
    await callback.message.answer(
        "🌎 <b>¿En qué país vives?</b>\n\n"
        "Este dato permite búsquedas internacionales y Travel Mode. "
        "No mostramos tu ubicación exacta.",
        reply_markup=onboarding_country_keyboard(),
    )


@router.callback_query(Onboarding.country, F.data.startswith("onbcountry:"))
async def onboarding_country_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    code = callback.data.split(":", 1)[1]

    if code == "other":
        await callback.answer()
        await callback.message.answer(
            "🌍 Escribe el código de dos letras de tu país. "
            "Ejemplo: <code>MX</code>, <code>CO</code>, <code>ES</code>."
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        await set_home_country(session, user, code)

    await callback.answer("País guardado")
    await state.set_state(Onboarding.location)
    await callback.message.answer(
        f"✅ País: <b>{country_label(code)}</b>\\n\\n"
        "📍 Ahora puedes compartir tu ubicación para encontrar personas "
        "cercanas. Tu coordenada exacta nunca se muestra.",
        reply_markup=location_keyboard(),
    )


@router.message(Onboarding.country)
async def onboarding_country_manual(
    message: Message,
    state: FSMContext,
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
        await set_home_country(session, user, code)

    await state.set_state(Onboarding.location)
    await message.answer(
        f"✅ País: <b>{country_label(code)}</b>\\n\\n"
        "📍 Ahora puedes compartir tu ubicación para encontrar personas cercanas.",
        reply_markup=location_keyboard(),
    )


@router.message(Onboarding.location, F.location)
async def onboarding_location(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        user.latitude = message.location.latitude
        user.longitude = message.location.longitude
        user.location_updated_at = datetime.now(timezone.utc)
        user.onboarding_completed = True
        await session.commit()

    await state.clear()
    await message.answer(
        "✅ <b>Perfil creado.</b>\n\n"
        "Ya puedes empezar a conocer personas.",
        reply_markup=main_menu(),
    )
    await message.answer(
        "🎯 <b>Mejora tus matches</b>\n\n"
        "Selecciona hasta 6 intereses para calcular mejor la compatibilidad.",
        reply_markup=interests_keyboard(set()),
    )


@router.message(Onboarding.location, F.text == "⏭ Omitir por ahora")
async def onboarding_skip_location(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        user.onboarding_completed = True
        await session.commit()

    await state.clear()
    await message.answer(
        "✅ <b>Perfil creado.</b>\n\n"
        "Puedes compartir tu ubicación más adelante desde tu perfil.",
        reply_markup=main_menu(),
    )
    await message.answer(
        "🎯 <b>Mejora tus matches</b>\n\n"
        "Selecciona hasta 6 intereses para calcular mejor la compatibilidad.",
        reply_markup=interests_keyboard(set()),
    )
