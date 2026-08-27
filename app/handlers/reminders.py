from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.database import SessionLocal
from app.keyboards import (
    adult_keyboard,
    gender_keyboard,
    location_keyboard,
)
from app.repositories import get_user_by_telegram
from app.services.growth import get_growth_profile
from app.states import Onboarding


router = Router(name="reminders")


@router.callback_query(F.data == "reminder:resume_onboarding")
async def resume_onboarding(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        if user.onboarding_completed:
            await callback.answer("Tu registro ya está completo")
            await callback.message.answer(
                "✅ Tu registro ya está completo. Puedes usar FreXo normalmente."
            )
            return

        if not user.adult_confirmed:
            await callback.answer()
            await callback.message.answer(
                "🔞 <b>Confirma que eres mayor de 18 años para continuar.</b>",
                reply_markup=adult_keyboard(),
            )
            return

        if not user.alias:
            await state.set_state(Onboarding.alias)
            await callback.answer()
            await callback.message.answer(
                "👤 <b>Continuemos tu perfil.</b>\n\n"
                "¿Cómo quieres que te llamen dentro de FreXo?"
            )
            return

        if not user.birth_date:
            await state.set_state(Onboarding.birth_date)
            await callback.answer()
            await callback.message.answer(
                "🎂 Escribe tu fecha de nacimiento en formato <b>DD/MM/AAAA</b>."
            )
            return

        if not user.gender:
            await state.set_state(Onboarding.gender)
            await callback.answer()
            await callback.message.answer(
                "🚻 <b>¿Cómo quieres aparecer en FreXo?</b>",
                reply_markup=gender_keyboard("gender"),
            )
            return

        growth = await get_growth_profile(session, user)
        await session.commit()

        if growth.home_country_code:
            await state.set_state(Onboarding.location)
            await callback.answer()
            await callback.message.answer(
                "📍 <b>Último paso.</b>\n\n"
                "Comparte tu ubicación para encontrar personas cerca o elige omitirla.",
                reply_markup=location_keyboard(),
            )
            return

    # Como seeking_gender tiene 'any' como valor por defecto, si aún no hay
    # país volvemos a confirmar esta preferencia antes de continuar.
    await state.set_state(Onboarding.seeking_gender)
    await callback.answer()
    await callback.message.answer(
        "❤️ <b>¿A quién quieres conocer?</b>",
        reply_markup=gender_keyboard("seeking"),
    )
