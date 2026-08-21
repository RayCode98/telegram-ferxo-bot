from __future__ import annotations
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.config import settings
from app.database import SessionLocal
from app.repositories import get_user_by_telegram
from app.services.lifecycle import delete_account, reactivate_account

router=Router(name="support")

def safety_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Ayuda",callback_data="support:help"),InlineKeyboardButton(text="🔐 Privacidad",callback_data="support:privacy")],
        [InlineKeyboardButton(text="📜 Términos",callback_data="support:terms"),InlineKeyboardButton(text="🛡️ Comunidad",callback_data="support:community")],
        [InlineKeyboardButton(text="🗑 Eliminar mi cuenta",callback_data="account:delete")],
        [InlineKeyboardButton(text="🏠 Inicio",callback_data="nav:home")],
    ])

@router.message(F.text == "🛡️ Seguridad")
async def safety_hub(message: Message) -> None:
    await message.answer("🛡️ <b>Seguridad y ayuda</b>\n\n• Tu Telegram permanece oculto salvo consentimiento mutuo.\n• Tu ubicación exacta nunca se muestra.\n• Bloquear y reportar siempre es gratuito.\n• Un pago nunca permite saltarse un bloqueo o consentimiento.",reply_markup=safety_hub_keyboard())

@router.message(F.text == "/help")
async def help_command(message: Message) -> None:
    await show_help(message)

@router.callback_query(F.data == "support:help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer(); await show_help(callback.message)

async def show_help(message: Message) -> None:
    await message.answer("❓ <b>Centro de ayuda FreXo</b>\n\n🎲 Buscar: encuentra una conexión compatible.\n👀 Conocer más: perfil ampliado sólo si ambos aceptan.\n📲 Compartir Telegram: requiere doble consentimiento.\n↩️ Reconectar: envía una solicitud; la otra persona decide.\n👑 Premium/Stars: usa /paysupport para problemas de pago.\n\nSoporte: " + settings.support_username)

@router.callback_query(F.data == "support:privacy")
async def privacy(callback: CallbackQuery) -> None:
    await callback.answer(); await callback.message.answer("🔐 <b>Privacidad de FreXo</b>\n\nFreXo usa los datos que proporcionas para crear tu perfil, calcular compatibilidad, aplicar seguridad y procesar beneficios comprados. No almacenamos el texto de tus conversaciones como historial; sí registramos métricas operativas como conteos, estados y reportes.\n\nLa ubicación exacta no se muestra a otros usuarios. Los pagos digitales se procesan con Telegram Stars. Si eliminas tu cuenta, el perfil se anonimiza; ciertos registros de pagos y seguridad pueden conservarse para integridad operativa, fraude y obligaciones aplicables.\n\nVigente desde: <b>"+settings.legal_effective_date+"</b>.")

@router.callback_query(F.data == "support:terms")
async def terms(callback: CallbackQuery) -> None:
    await callback.answer(); await callback.message.answer("📜 <b>Términos esenciales de FreXo</b>\n\n• Servicio exclusivo para personas de 18 años o más.\n• No se permite acoso, amenazas, fraude, spam ni suplantación.\n• Los productos digitales se cobran en Telegram Stars y no garantizan que otra persona acepte interactuar contigo.\n• FreXo puede restringir cuentas que incumplan las normas.\n• Funciones, precios y límites pueden cambiar con aviso dentro del servicio.\n\nEstos textos son una base operativa; antes de una campaña comercial amplia conviene revisión jurídica local.")

@router.callback_query(F.data == "support:community")
async def community(callback: CallbackQuery) -> None:
    await callback.answer(); await callback.message.answer("🛡️ <b>Normas de la comunidad</b>\n\n1. Respeta consentimiento y límites.\n2. No compartas contenido sexual no solicitado.\n3. No solicites dinero, contraseñas o códigos de acceso.\n4. No suplantes identidades ni automatices acoso.\n5. Si sospechas que alguien es menor, termina y reporta.\n6. Usa Bloquear/Reportar cuando sea necesario.")

@router.callback_query(F.data == "account:delete")
async def delete_prompt(callback: CallbackQuery) -> None:
    await callback.answer(); await callback.message.answer("⚠️ <b>Eliminar tu cuenta FreXo</b>\n\nTu perfil dejará de aparecer, se terminará cualquier conversación activa y se anonimizarán tus datos de perfil. Registros necesarios de pagos y seguridad pueden conservarse.\n\n¿Deseas continuar?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Sí, eliminar",callback_data="account:delete_confirm")],[InlineKeyboardButton(text="❌ Cancelar",callback_data="nav:home")]]))

@router.callback_query(F.data == "account:delete_confirm")
async def delete_confirm(callback: CallbackQuery) -> None:
    partner=None
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        partner=await delete_account(session,user)
    if partner:
        try: await callback.bot.send_message(partner,"🤖 <b>FreXo</b>\n\n👋 Tu conexión cerró su cuenta. La conversación terminó.")
        except Exception: pass
    await callback.answer("Cuenta eliminada"); await callback.message.answer("🗑 <b>Tu cuenta FreXo fue eliminada.</b>\n\nTu perfil ya no participa en búsquedas. Si deseas volver, usa /start para reactivar el acceso desde cero.")

@router.callback_query(F.data == "account:reactivate")
async def reactivate(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user=await get_user_by_telegram(session,callback.from_user.id)
        if not user: return
        await reactivate_account(session,user)
    await callback.answer("Cuenta reactivada"); await callback.message.answer("✅ Cuenta reactivada. Usa /start nuevamente para completar tu perfil.")
