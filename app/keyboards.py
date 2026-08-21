from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def adult_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Soy mayor de 18", callback_data="adult:yes")],
            [InlineKeyboardButton(text="❌ Salir", callback_data="adult:no")],
        ]
    )


def gender_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Hombre", callback_data=f"{prefix}:male"),
                InlineKeyboardButton(text="👩 Mujer", callback_data=f"{prefix}:female"),
            ],
            [
                InlineKeyboardButton(text="✨ Otro", callback_data=f"{prefix}:other"),
                InlineKeyboardButton(text="🌍 Cualquiera", callback_data=f"{prefix}:any"),
            ],
        ]
    )


def location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Compartir ubicación", request_location=True)],
            [KeyboardButton(text="⏭ Omitir por ahora")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎲 Buscar persona"),
                KeyboardButton(text="📍 Personas cerca"),
            ],
            [
                KeyboardButton(text="❤️ Likes recibidos"),
                KeyboardButton(text="👤 Mi perfil"),
            ],
            [
                KeyboardButton(text="👑 Premium"),
                KeyboardButton(text="⚙️ Preferencias"),
            ],
            [
                KeyboardButton(text="🛡️ Seguridad"),
            ],
        ],
        resize_keyboard=True,
    )


def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Alias", callback_data="profile:alias"),
                InlineKeyboardButton(text="📝 Bio", callback_data="profile:bio"),
            ],
            [
                InlineKeyboardButton(text="📸 Foto", callback_data="profile:photo"),
                InlineKeyboardButton(text="📍 Ubicación", callback_data="profile:location"),
            ],
        ]
    )


def preferences_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ A quién conocer",
                    callback_data="prefs:seeking",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎂 Rango de edad",
                    callback_data="prefs:age",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📍 Distancia",
                    callback_data="prefs:distance",
                )
            ],
        ]
    )


def distance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5 km", callback_data="distance:5"),
                InlineKeyboardButton(text="10 km", callback_data="distance:10"),
            ],
            [
                InlineKeyboardButton(text="25 km", callback_data="distance:25"),
                InlineKeyboardButton(text="50 km", callback_data="distance:50"),
            ],
            [
                InlineKeyboardButton(text="100 km", callback_data="distance:100"),
            ],
        ]
    )


def search_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar búsqueda", callback_data="search:cancel")]
        ]
    )


def active_chat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Ver perfil", callback_data="chat:profile"),
                InlineKeyboardButton(text="👀 Conocer más", callback_data="chat:know_more"),
            ],
            [
                InlineKeyboardButton(text="❤️ Me interesa", callback_data="chat:like"),
                InlineKeyboardButton(text="💘 Super Interés", callback_data="chat:super"),
            ],
            [
                InlineKeyboardButton(text="📲 Compartir Telegram", callback_data="chat:share_contact"),
            ],
            [
                InlineKeyboardButton(text="🔄 Siguiente", callback_data="chat:next"),
                InlineKeyboardButton(text="❌ Terminar", callback_data="chat:end"),
            ],
            [
                InlineKeyboardButton(text="🚫 Bloquear", callback_data="chat:block"),
                InlineKeyboardButton(text="🚨 Reportar", callback_data="chat:report"),
            ],
        ]
    )


def reconnect_after_chat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Intentar reconectar",
                    callback_data="reconnect:request",
                )
            ]
        ]
    )


def reconnect_request_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Aceptar reconexión",
                    callback_data=f"reconnect:accept:{request_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rechazar",
                    callback_data=f"reconnect:decline:{request_id}",
                )
            ],
        ]
    )


def like_back_keyboard(user_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Devolver interés",
                    callback_data=f"likes:back:{user_id}",
                )
            ]
        ]
    )


def store_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👑 Premium · 199 ⭐/mes",
                    callback_data="buy:premium_monthly",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Boost 30 min · 25 ⭐",
                    callback_data="buy:boost_30m",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💘 Super Interés · 10 ⭐",
                    callback_data="buy:super_interest",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Reconectar · 15 ⭐",
                    callback_data="buy:reconnect",
                )
            ],
        ]
    )


def report_keyboard() -> InlineKeyboardMarkup:
    reasons = [
        ("🔞 Contenido sexual no solicitado", "sexual"),
        ("🤬 Acoso / insultos", "harassment"),
        ("🤖 Spam / estafa", "spam"),
        ("🧒 Posible menor de edad", "minor"),
        ("⚠️ Otro", "other"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"report:{value}")]
            for label, value in reasons
        ]
    )
