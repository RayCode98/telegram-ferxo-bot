from __future__ import annotations

from html import escape
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import (
    active_chat_keyboard,
    like_back_keyboard,
    reconnect_request_keyboard,
    store_keyboard,
)
from app.models import Conversation, ReconnectRequest
from app.repositories import (
    add_interest,
    consume,
    create_conversation,
    create_reconnect_request,
    get_last_reconnectable_conversation,
    get_user_by_id,
    get_user_by_telegram,
    profile_reveal_is_mutual,
    received_interest_count,
    received_interests,
    set_contact_share_consent,
    set_profile_reveal_consent,
)
from app.services.matchmaking import (
    get_active_partner,
    set_active_pair,
)
from app.services.profile import premium_active, send_profile_card


router = Router(name="social")


@router.message(F.text == "❤️ Likes recibidos")
async def likes_received(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user:
            return

        count = await received_interest_count(session, user)
        if count == 0:
            await message.answer(
                "❤️ Todavía no tienes personas interesadas.\n\n"
                "Sigue conversando: cuando alguien marque «Me interesa», aparecerá aquí."
            )
            return

        if not premium_active(user):
            await message.answer(
                f"❤️ <b>{count} persona{'s' if count != 1 else ''}</b> "
                "mostraron interés en ti.\n\n"
                "👑 Con FreXo Premium puedes descubrir quiénes son y ver sus perfiles.",
                reply_markup=store_keyboard(),
            )
            return

        likes = await received_interests(session, user, limit=10)

        await message.answer(
            f"❤️ <b>Personas interesadas en ti: {count}</b>\n\n"
            "Mostrando las más recientes:"
        )
        for interest, sender in likes:
            await send_profile_card(
                message.bot,
                message.chat.id,
                sender,
                viewer=user,
                reply_markup=like_back_keyboard(sender.id),
                force_full=True,
            )


@router.callback_query(F.data.startswith("likes:back:"))
async def like_back(callback: CallbackQuery) -> None:
    sender_user_id = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        sender = await get_user_by_id(session, sender_user_id)
        if not user or not sender:
            await callback.answer("Perfil no disponible.", show_alert=True)
            return
        if not premium_active(user):
            await callback.answer("Esta sección requiere Premium.", show_alert=True)
            return

        _, mutual = await add_interest(
            session,
            user,
            sender,
            conversation_id=None,
            is_super=False,
        )

    await callback.answer("Interés enviado ❤️")
    if mutual:
        await callback.message.answer(
            "💘 <b>¡Ahora el interés es mutuo!</b>\n\n"
            "Si vuelven a coincidir, FreXo lo tendrá en cuenta en la experiencia."
        )
        await callback.bot.send_message(
            sender.telegram_id,
            "💘 <b>¡Tienes un nuevo interés mutuo!</b>"
        )


@router.callback_query(F.data == "chat:know_more")
async def know_more(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay una conversación activa.", show_alert=True)
        return

    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        conversation = await session.get(Conversation, conversation_id)
        if not user or not partner or not conversation:
            return

        mutual = await set_profile_reveal_consent(
            session,
            conversation,
            user,
        )

        if not mutual:
            await callback.answer("Solicitud guardada 👀")
            await callback.message.answer(
                "👀 Le hicimos saber a la otra persona que quieres conocerla mejor.\n\n"
                "Tu perfil ampliado sólo se revelará si también acepta."
            )
            await callback.bot.send_message(
                partner_tg,
                "👀 <b>La persona con la que hablas quiere conocerte mejor.</b>\n\n"
                "Si también quieres, pulsa «👀 Conocer más» en los controles del chat.",
                reply_markup=active_chat_keyboard(),
            )
            return

        await callback.answer("¡Ambos aceptaron! 🤝")

        await callback.message.answer(
            "🤝 <b>¡Ambos aceptaron conocerse mejor!</b>\n\n"
            "FreXo desbloqueó el perfil ampliado para los dos."
        )
        await send_profile_card(
            callback.bot,
            callback.from_user.id,
            partner,
            viewer=user,
            reply_markup=active_chat_keyboard(),
            force_full=True,
        )

        await callback.bot.send_message(
            partner_tg,
            "🤝 <b>¡Ambos aceptaron conocerse mejor!</b>\n\n"
            "FreXo desbloqueó el perfil ampliado para los dos."
        )
        await send_profile_card(
            callback.bot,
            partner_tg,
            user,
            viewer=partner,
            reply_markup=active_chat_keyboard(),
            force_full=True,
        )


@router.callback_query(F.data == "chat:share_contact")
async def share_contact(callback: CallbackQuery) -> None:
    active = await get_active_partner(callback.from_user.id)
    if not active:
        await callback.answer("No hay una conversación activa.", show_alert=True)
        return

    partner_tg, conversation_id = active

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        partner = await get_user_by_telegram(session, partner_tg)
        conversation = await session.get(Conversation, conversation_id)
        if not user or not partner or not conversation:
            return

        # Primero ambos deben haber aceptado conocerse mejor.
        if not await profile_reveal_is_mutual(session, conversation_id):
            await callback.answer(
                "Primero ambos deben aceptar «Conocer más».",
                show_alert=True,
            )
            return

        mutual = await set_contact_share_consent(
            session,
            conversation,
            user,
        )

        if not mutual:
            await callback.answer("Consentimiento guardado 📲")
            await callback.message.answer(
                "📲 Aceptaste compartir tu Telegram.\n\n"
                "No mostraremos ningún contacto hasta que la otra persona también acepte."
            )
            await callback.bot.send_message(
                partner_tg,
                "📲 La otra persona está dispuesta a compartir su Telegram.\n\n"
                "Si tú también quieres, pulsa «📲 Compartir Telegram»."
            )
            return

        user_link = (
            f'<a href="tg://user?id={user.telegram_id}">'
            f'{escape(user.alias or "Abrir perfil")}</a>'
        )
        partner_link = (
            f'<a href="tg://user?id={partner.telegram_id}">'
            f'{escape(partner.alias or "Abrir perfil")}</a>'
        )

    await callback.answer("Contactos compartidos 🤝")
    await callback.message.answer(
        "🤝 <b>Ambos aceptaron compartir su Telegram.</b>\n\n"
        f"📲 {partner_link}"
    )
    await callback.bot.send_message(
        partner_tg,
        "🤝 <b>Ambos aceptaron compartir su Telegram.</b>\n\n"
        f"📲 {user_link}"
    )


@router.callback_query(F.data == "reconnect:request")
async def reconnect_request(callback: CallbackQuery) -> None:
    if await get_active_partner(callback.from_user.id):
        await callback.answer(
            "Termina tu conversación actual antes de reconectar.",
            show_alert=True,
        )
        return

    async with SessionLocal() as session:
        user = await get_user_by_telegram(session, callback.from_user.id)
        if not user:
            return

        candidate = await get_last_reconnectable_conversation(session, user)
        if not candidate:
            await callback.answer(
                "No tienes una conversación elegible para reconectar.",
                show_alert=True,
            )
            return

        source_conversation, partner = candidate

        # Sólo consumimos el crédito cuando tenemos un destino válido.
        if not await consume(session, user, "reconnect", 1):
            await callback.answer(
                "Necesitas 1 crédito de Reconexión.",
                show_alert=True,
            )
            await callback.message.answer(
                "↩️ No tienes créditos de Reconexión.\n\n"
                "Puedes obtener uno en la tienda por 15 ⭐.",
                reply_markup=store_keyboard(),
            )
            return

        request = await create_reconnect_request(
            session,
            source_conversation,
            user,
            partner,
        )

    await callback.answer("Solicitud enviada ↩️")
    await callback.message.answer(
        "↩️ <b>Solicitud de reconexión enviada.</b>\n\n"
        "La otra persona decidirá si quiere volver a hablar. "
        "Nunca se fuerza una reconexión."
    )
    await callback.bot.send_message(
        partner.telegram_id,
        "↩️ <b>Una persona con la que hablaste quiere reconectar.</b>\n\n"
        "Puedes aceptar o rechazar. Tu identidad sigue protegida.",
        reply_markup=reconnect_request_keyboard(request.id),
    )


@router.callback_query(F.data.startswith("reconnect:decline:"))
async def reconnect_decline(callback: CallbackQuery) -> None:
    request_id = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        request = await session.get(ReconnectRequest, request_id)
        if (
            not request
            or request.target_id is None
            or request.status != "pending"
        ):
            await callback.answer("Solicitud no disponible.", show_alert=True)
            return

        target = await get_user_by_telegram(session, callback.from_user.id)
        if not target or target.id != request.target_id:
            await callback.answer("Solicitud no válida.", show_alert=True)
            return

        request.status = "declined"
        requester = await get_user_by_id(session, request.requester_id)
        await session.commit()

    await callback.answer("Reconexión rechazada")
    await callback.message.edit_text("❌ Rechazaste la solicitud de reconexión.")
    if requester:
        await callback.bot.send_message(
            requester.telegram_id,
            "↩️ La otra persona no aceptó la reconexión."
        )


@router.callback_query(F.data.startswith("reconnect:accept:"))
async def reconnect_accept(callback: CallbackQuery) -> None:
    request_id = callback.data.split(":", 2)[2]

    async with SessionLocal() as session:
        request = await session.get(ReconnectRequest, request_id)
        target = await get_user_by_telegram(session, callback.from_user.id)

        if not request or not target or request.target_id != target.id:
            await callback.answer("Solicitud no válida.", show_alert=True)
            return

        if request.status != "pending":
            await callback.answer("Esta solicitud ya fue procesada.", show_alert=True)
            return

        if request.expires_at <= datetime.now(timezone.utc):
            request.status = "expired"
            await session.commit()
            await callback.answer("La solicitud expiró.", show_alert=True)
            return

        requester = await get_user_by_id(session, request.requester_id)
        if not requester:
            request.status = "declined"
            await session.commit()
            return

        if await get_active_partner(target.telegram_id) or await get_active_partner(
            requester.telegram_id
        ):
            await callback.answer(
                "Alguno de los dos está conversando ahora. Inténtalo después.",
                show_alert=True,
            )
            return

        # Volvemos a verificar que la conversación original siga siendo elegible.
        from app.repositories import are_blocked
        if await are_blocked(session, requester, target):
            request.status = "declined"
            await session.commit()
            await callback.answer("La reconexión ya no está disponible.", show_alert=True)
            return

        conversation = await create_conversation(session, requester, target)
        request.status = "accepted"
        await session.commit()
        await set_active_pair(requester, target, conversation.id)

    await callback.answer("Reconexión aceptada 🎉")
    await callback.message.edit_text(
        "🎉 <b>Reconexión aceptada.</b>\n\nYa pueden volver a conversar."
    )
    await callback.message.answer(
        "Controles de la conversación:",
        reply_markup=active_chat_keyboard(),
    )
    await callback.bot.send_message(
        requester.telegram_id,
        "🎉 <b>¡Aceptaron tu reconexión!</b>\n\nYa pueden volver a conversar.",
        reply_markup=active_chat_keyboard(),
    )
