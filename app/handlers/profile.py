from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.database import SessionLocal
from app.keyboards import (
    distance_keyboard,
    gender_keyboard,
    location_keyboard,
    main_menu,
    preferences_menu,
    profile_menu,
    nav_home_keyboard,
)
from app.repositories import get_user_by_telegram
from app.services.matchmaking import age_of
from app.services.profile import gender_label, premium_active, send_profile_card
from app.services.growth import received_gift_count
from app.services.social_graph import get_experience_preferences, toggle_activity_visibility, toggle_smart_notifications
from app.states import EditProfile, Preferences


router = Router(name="profile")


@router.message(F.text == "👤 Mi perfil")
async def my_profile(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        gifts = await received_gift_count(session, user)

        await send_profile_card(
            message.bot,
            message.chat.id,
            user,
            reply_markup=profile_menu(),
        )
        await message.answer(
            f"🎁 Regalos virtuales recibidos: <b>{gifts}</b>"
        )


@router.callback_query(F.data == "profile:alias")
async def edit_alias(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.alias)
    await callback.answer()
    await callback.message.answer(
        "✏️ Escribe tu nuevo alias (2–40 caracteres).",
        reply_markup=nav_home_keyboard(),
    )


@router.message(EditProfile.alias)
async def save_alias(message: Message, state: FSMContext) -> None:
    alias = (message.text or "").strip()
    if not 2 <= len(alias) <= 40:
        await message.answer("El alias debe tener entre 2 y 40 caracteres.")
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        user.alias = alias
        await session.commit()

    await state.clear()
    await message.answer("✅ Alias actualizado.", reply_markup=main_menu())


@router.callback_query(F.data == "profile:bio")
async def edit_bio(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.bio)
    await callback.answer()
    await callback.message.answer(
        "📝 Escribe una descripción corta sobre ti.\n\n"
        "Máximo 300 caracteres. Para borrarla escribe <code>-</code>.",
        reply_markup=nav_home_keyboard(),
    )


@router.message(EditProfile.bio)
async def save_bio(message: Message, state: FSMContext) -> None:
    bio = (message.text or "").strip()
    if bio != "-" and not 1 <= len(bio) <= 300:
        await message.answer("La descripción debe tener máximo 300 caracteres.")
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        user.bio = None if bio == "-" else bio
        await session.commit()

    await state.clear()
    await message.answer("✅ Descripción actualizada.", reply_markup=main_menu())


@router.callback_query(F.data == "profile:photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.photo)
    await callback.answer()
    await callback.message.answer(
        "📸 Envíame una foto para usarla en tu perfil.\n\n"
        "Para eliminar tu foto escribe <code>-</code>."
    )


@router.message(EditProfile.photo, F.photo)
async def save_photo(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        user.photo_file_id = file_id
        await session.commit()

    await state.clear()
    await message.answer("✅ Foto de perfil actualizada.", reply_markup=main_menu())


@router.message(EditProfile.photo, F.text == "-")
async def delete_photo(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        user.photo_file_id = None
        await session.commit()

    await state.clear()
    await message.answer("✅ Foto eliminada.", reply_markup=main_menu())


@router.message(EditProfile.photo)
async def invalid_photo(message: Message) -> None:
    await message.answer("Envíame una fotografía o escribe <code>-</code> para eliminarla.")


@router.callback_query(F.data == "profile:location")
async def ask_profile_location(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "📍 Comparte tu ubicación actual.\n\n"
        "FreXo sólo la utiliza para calcular distancias aproximadas.",
        reply_markup=location_keyboard(),
    )


@router.message(F.text == "⚙️ Preferencias")
async def preferences(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        premium = premium_active(user)
        premium_badge = "👑 Activo" if premium else "🔒 Requiere Premium"
        experience = await get_experience_preferences(session, user)
        await message.answer(
            "⚙️ <b>Preferencias</b>\n\n"
            f"❤️ Buscar: {gender_label(user.seeking_gender)}\n"
            f"🎂 Edad: {user.min_age}–{user.max_age}\n"
            f"📍 Radio: {user.max_distance_km} km\n"
            f"🟢 Mostrar actividad: {'Sí' if experience.show_activity_status else 'No'}\n"
            f"🔔 Avisos compatibles: {'Sí' if experience.smart_notifications else 'No'}\n\n"
            f"🎯 Filtros avanzados: {premium_badge}",
            reply_markup=preferences_menu(experience.show_activity_status, experience.smart_notifications),
        )


@router.callback_query(F.data == "prefs:seeking")
async def edit_seeking(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "❤️ ¿A quién quieres conocer?",
        reply_markup=gender_keyboard("prefseeking"),
    )


@router.callback_query(F.data.startswith("prefseeking:"))
async def save_seeking(callback: CallbackQuery) -> None:
    value = callback.data.split(":", 1)[1]
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        user.seeking_gender = value
        await session.commit()

    await callback.answer("Preferencia actualizada")
    await callback.message.answer(
        f"✅ Ahora buscas: <b>{gender_label(value)}</b>."
    )


@router.callback_query(F.data == "prefs:age")
async def edit_age(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        if not premium_active(user):
            await callback.answer(
                "El filtro avanzado de edad requiere FreXo Premium.",
                show_alert=True,
            )
            return

    await state.set_state(Preferences.min_age)
    await callback.answer()
    await callback.message.answer(
        "🎂 Escribe la <b>edad mínima</b> que quieres encontrar (18–99)."
    )


@router.message(Preferences.min_age)
async def save_min_age(message: Message, state: FSMContext) -> None:
    try:
        value = int((message.text or "").strip())
    except ValueError:
        await message.answer("Escribe un número entre 18 y 99.")
        return

    if not 18 <= value <= 99:
        await message.answer("La edad mínima debe estar entre 18 y 99.")
        return

    await state.update_data(min_age=value)
    await state.set_state(Preferences.max_age)
    await message.answer(
        f"✅ Mínima: {value}.\n\n"
        "Ahora escribe la <b>edad máxima</b> (18–99)."
    )


@router.message(Preferences.max_age)
async def save_max_age(message: Message, state: FSMContext) -> None:
    try:
        max_age = int((message.text or "").strip())
    except ValueError:
        await message.answer("Escribe un número entre 18 y 99.")
        return

    data = await state.get_data()
    min_age = int(data["min_age"])

    if not min_age <= max_age <= 99:
        await message.answer(
            f"La edad máxima debe estar entre {min_age} y 99."
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return
        user.min_age = min_age
        user.max_age = max_age
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Rango actualizado a <b>{min_age}–{max_age}</b>.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "prefs:distance")
async def edit_distance(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return
        if not premium_active(user):
            await callback.answer(
                "Elegir un radio preciso requiere FreXo Premium. "
                "La búsqueda gratuita usa hasta 100 km.",
                show_alert=True,
            )
            return

    await callback.answer()
    await callback.message.answer(
        "📍 Selecciona el radio máximo para <b>Personas cerca</b>:",
        reply_markup=distance_keyboard(),
    )


@router.callback_query(F.data.startswith("distance:"))
async def save_distance(callback: CallbackQuery) -> None:
    try:
        value = int(callback.data.split(":", 1)[1])
    except ValueError:
        return

    if value not in {5, 10, 25, 50, 100}:
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user or not premium_active(user):
            await callback.answer(
                "Esta opción requiere FreXo Premium.",
                show_alert=True,
            )
            return
        user.max_distance_km = value
        await session.commit()

    await callback.answer("Distancia actualizada")
    await callback.message.edit_text(
        f"✅ Radio máximo configurado en <b>{value} km</b>."
    )


@router.message(F.location)
async def update_location(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user or not user.onboarding_completed:
            return

        user.latitude = message.location.latitude
        user.longitude = message.location.longitude
        user.location_updated_at = datetime.now(timezone.utc)
        await session.commit()

    await message.answer(
        "📍 Ubicación actualizada. Nunca se mostrará tu coordenada exacta.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "⏭ Omitir por ahora")
async def skip_location_menu(message: Message) -> None:
    await message.answer(
        "Sin cambios en tu ubicación.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "🛡️ Seguridad")
async def safety(message: Message) -> None:
    await message.answer(
        "🛡️ <b>Seguridad en FreXo</b>\n\n"
        "• No compartimos tu Telegram automáticamente.\n"
        "• Tu ubicación exacta nunca se muestra a otra persona.\n"
        "• Puedes terminar, bloquear o reportar una conversación.\n"
        "• Un pago nunca permite saltarse un bloqueo ni el consentimiento.\n"
        "• Si alguien te solicita datos sensibles, termina y reporta."
    )


@router.callback_query(F.data == "prefs:toggle_activity")
async def toggle_activity_pref(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user: return
        await toggle_activity_visibility(session, user)
        prefs = await get_experience_preferences(session, user)
    await callback.answer("Preferencia actualizada")
    await callback.message.edit_reply_markup(reply_markup=preferences_menu(prefs.show_activity_status, prefs.smart_notifications))

@router.callback_query(F.data == "prefs:toggle_notifications")
async def toggle_notifications_pref(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user: return
        await toggle_smart_notifications(session, user)
        prefs = await get_experience_preferences(session, user)
    await callback.answer("Preferencia actualizada")
    await callback.message.edit_reply_markup(reply_markup=preferences_menu(prefs.show_activity_status, prefs.smart_notifications))
