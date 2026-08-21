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



def onboarding_country_keyboard() -> InlineKeyboardMarkup:
    countries = [
        ("🇲🇽 México", "MX"),
        ("🇨🇴 Colombia", "CO"),
        ("🇦🇷 Argentina", "AR"),
        ("🇪🇸 España", "ES"),
        ("🇺🇸 EE.UU.", "US"),
        ("🇨🇱 Chile", "CL"),
        ("🇵🇪 Perú", "PE"),
        ("🇻🇪 Venezuela", "VE"),
        ("🇧🇷 Brasil", "BR"),
        ("🇪🇨 Ecuador", "EC"),
        ("🇬🇹 Guatemala", "GT"),
        ("🇩🇴 Rep. Dominicana", "DO"),
    ]
    rows = []
    for index in range(0, len(countries), 2):
        row = [
            InlineKeyboardButton(
                text=label,
                callback_data=f"onbcountry:{code}",
            )
            for label, code in countries[index:index + 2]
        ]
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="🌍 Otro país",
                callback_data="onbcountry:other",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
            [KeyboardButton(text="🎲 Buscar persona"), KeyboardButton(text="📍 Personas cerca")],
            [KeyboardButton(text="❤️ Likes recibidos"), KeyboardButton(text="👤 Mi perfil")],
            [KeyboardButton(text="🕘 Historial"), KeyboardButton(text="⭐ Favoritos")],
            [KeyboardButton(text="🌎 Explorar"), KeyboardButton(text="🎁 Recompensas")],
            [KeyboardButton(text="👑 Premium"), KeyboardButton(text="⚙️ Preferencias")],
            [KeyboardButton(text="🛡️ Seguridad")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Elige una opción de FreXo…",
    )



def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Alias", callback_data="profile:alias"), InlineKeyboardButton(text="📝 Bio", callback_data="profile:bio")],
        [InlineKeyboardButton(text="📸 Foto", callback_data="profile:photo"), InlineKeyboardButton(text="📍 Ubicación", callback_data="profile:location")],
        [InlineKeyboardButton(text="🎯 Mis intereses", callback_data="profile:interests")],
        [InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")],
    ])



def preferences_menu(show_activity: bool = True, smart_notifications: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ A quién conocer", callback_data="prefs:seeking")],
        [InlineKeyboardButton(text="🎂 Rango de edad", callback_data="prefs:age")],
        [InlineKeyboardButton(text="📍 Distancia", callback_data="prefs:distance")],
        [InlineKeyboardButton(text=("🟢 Actividad visible: Sí" if show_activity else "⚪ Actividad visible: No"), callback_data="prefs:toggle_activity")],
        [InlineKeyboardButton(text=("🔔 Avisos compatibles: Sí" if smart_notifications else "🔕 Avisos compatibles: No"), callback_data="prefs:toggle_notifications")],
        [InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")],
    ])


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
            [
                InlineKeyboardButton(text="⬅️ Atrás", callback_data="nav:prefs"),
                InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
            ],
        ]
    )



def search_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Cancelar búsqueda",
                    callback_data="search:cancel",
                )
            ],
            [
                InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
            ],
        ]
    )



def active_chat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧭 Panel de conversación",
                    callback_data="chat:panel",
                )
            ],
            [
                InlineKeyboardButton(text="👤 Ver perfil", callback_data="chat:profile"),
                InlineKeyboardButton(text="👀 Conocer más", callback_data="chat:know_more"),
            ],
            [
                InlineKeyboardButton(text="❤️ Me interesa", callback_data="chat:like"),
                InlineKeyboardButton(text="💘 Super Interés", callback_data="chat:super"),
            ],
            [
                InlineKeyboardButton(text="🎁 Enviar regalo", callback_data="chat:gift"),
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
            ],
            [
                InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
            ],
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
                ),
                InlineKeyboardButton(
                    text="🚀 Boost 60 min · 45 ⭐",
                    callback_data="buy:boost_60m",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌎 Travel 24 h · 15 ⭐",
                    callback_data="buy:travel_24h",
                ),
                InlineKeyboardButton(
                    text="🔥 Spotlight 3 h · 50 ⭐",
                    callback_data="buy:spotlight_3h",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💘 Super Interés · 10 ⭐",
                    callback_data="buy:super_interest",
                ),
                InlineKeyboardButton(
                    text="↩️ Reconectar · 15 ⭐",
                    callback_data="buy:reconnect",
                ),
            ],
            [
                InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
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
        inline_keyboard=(
            [
                [InlineKeyboardButton(text=label, callback_data=f"report:{value}")]
                for label, value in reasons
            ]
            + [[InlineKeyboardButton(text="⬅️ Volver al chat", callback_data="chat:panel")]]
        )
    )



def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Estadísticas",
                    callback_data="admin:stats",
                ),
                InlineKeyboardButton(
                    text="🚨 Reportes",
                    callback_data="admin:reports",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Conversión",
                    callback_data="admin:conversion",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Usuarios activos",
                    callback_data="admin:active",
                )
            ],
        ]
    )


def admin_report_actions(report_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏳ Ban 24 h",
                    callback_data=f"admin:ban24:{report_id}",
                ),
                InlineKeyboardButton(
                    text="⛔ Ban permanente",
                    callback_data=f"admin:banperm:{report_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Marcar revisado",
                    callback_data=f"admin:dismiss:{report_id}",
                )
            ],
        ]
    )




def explore_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Configurar mi país",
                    callback_data="growth:home_country",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌎 Activar Travel Pass",
                    callback_data="growth:travel_activate",
                ),
                InlineKeyboardButton(
                    text="🔥 Activar Spotlight",
                    callback_data="growth:spotlight_activate",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Activar Boost gratis",
                    callback_data="growth:boost_reward",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Ir a la tienda",
                    callback_data="growth:store",
                )
            ],
            [
                InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
            ],
        ]
    )


def country_keyboard(purpose: str) -> InlineKeyboardMarkup:
    countries = [
        ("🇲🇽 México", "MX"),
        ("🇨🇴 Colombia", "CO"),
        ("🇦🇷 Argentina", "AR"),
        ("🇪🇸 España", "ES"),
        ("🇺🇸 EE.UU.", "US"),
        ("🇨🇱 Chile", "CL"),
        ("🇵🇪 Perú", "PE"),
        ("🇻🇪 Venezuela", "VE"),
        ("🇧🇷 Brasil", "BR"),
        ("🇪🇨 Ecuador", "EC"),
        ("🇬🇹 Guatemala", "GT"),
        ("🇩🇴 Rep. Dominicana", "DO"),
    ]
    rows = []
    for index in range(0, len(countries), 2):
        row = []
        for label, code in countries[index:index + 2]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"country:{purpose}:{code}",
                )
            )
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(
                text="🌍 Otro país (código)",
                callback_data=f"country:{purpose}:other",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Atrás", callback_data="nav:explore"),
            InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)



def gift_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌹 Rosa · 5 ⭐",
                    callback_data="gift:gift_rose",
                ),
                InlineKeyboardButton(
                    text="☕ Café · 10 ⭐",
                    callback_data="gift:gift_coffee",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💐 Flores · 25 ⭐",
                    callback_data="gift:gift_flowers",
                ),
                InlineKeyboardButton(
                    text="💎 Diamante · 100 ⭐",
                    callback_data="gift:gift_diamond",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Volver al chat",
                    callback_data="chat:panel",
                )
            ],
        ]
    )



def chat_reply_keyboard(page: int = 1) -> ReplyKeyboardMarkup:
    if page == 2:
        keyboard = [
            [KeyboardButton(text="💘 Super Interés"), KeyboardButton(text="📲 Compartir Telegram")],
            [KeyboardButton(text="🎁 Regalo"), KeyboardButton(text="⭐ Guardar favorito")],
            [KeyboardButton(text="🚫 Bloquear"), KeyboardButton(text="🚨 Reportar")],
            [KeyboardButton(text="🔄 Siguiente"), KeyboardButton(text="❌ Terminar")],
            [KeyboardButton(text="⬅️ Acciones principales")],
        ]
        placeholder = "Más acciones de tu conversación…"
    else:
        keyboard = [
            [KeyboardButton(text="🧭 Panel de chat"), KeyboardButton(text="👤 Mi conexión")],
            [KeyboardButton(text="❤️ Me interesa"), KeyboardButton(text="👀 Conocer más")],
            [KeyboardButton(text="🔄 Siguiente"), KeyboardButton(text="❌ Terminar")],
            [KeyboardButton(text="➡️ Más opciones")],
        ]
        placeholder = "Escribe a tu conexión…"
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True, input_field_placeholder=placeholder)


def nav_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")]
        ]
    )


def rewards_keyboard(can_claim: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if can_claim:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎁 Reclamar recompensa diaria",
                    callback_data="retention:daily",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)



INTEREST_LABELS = {
    "music": "🎵 Música", "travel": "✈️ Viajes", "gaming": "🎮 Videojuegos", "sports": "⚽ Deportes",
    "movies": "🎬 Cine/Series", "reading": "📚 Lectura", "fitness": "🏋️ Fitness", "food": "🍕 Comida",
    "nature": "🌿 Naturaleza", "tech": "💻 Tecnología", "pets": "🐾 Mascotas", "art": "🎨 Arte",
    "dance": "💃 Baile", "photography": "📸 Fotografía", "business": "💼 Negocios", "languages": "🌐 Idiomas",
}

def interests_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    rows=[]; items=list(INTEREST_LABELS.items())
    for i in range(0,len(items),2):
        row=[]
        for code,label in items[i:i+2]:
            row.append(InlineKeyboardButton(text=("✅ " if code in selected else "")+label, callback_data=f"interest:toggle:{code}"))
        rows.append(row)
    rows += [[InlineKeyboardButton(text="✅ Terminar", callback_data="interest:done")], [InlineKeyboardButton(text="⬅️ Perfil", callback_data="nav:profile"), InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def history_keyboard(page:int, has_prev:bool, has_next:bool) -> InlineKeyboardMarkup:
    row=[]
    if has_prev: row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"history:page:{page-1}"))
    if has_next: row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"history:page:{page+1}"))
    rows=[row] if row else []
    rows.append([InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def favorites_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Actualizar", callback_data="favorites:refresh")],[InlineKeyboardButton(text="🏠 Inicio", callback_data="nav:home")]])

def favorite_card_keyboard(user_id:str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Quitar favorito", callback_data=f"favorite:remove:{user_id}")]])
