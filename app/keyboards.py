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
                KeyboardButton(text="👤 Mi perfil"),
                KeyboardButton(text="👑 Premium"),
            ],
            [
                KeyboardButton(text="⚙️ Preferencias"),
                KeyboardButton(text="🛡️ Seguridad"),
            ],
        ],
        resize_keyboard=True,
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
                InlineKeyboardButton(text="❤️ Me interesa", callback_data="chat:like"),
                InlineKeyboardButton(text="💘 Super Interés", callback_data="chat:super"),
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
