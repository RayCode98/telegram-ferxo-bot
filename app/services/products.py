from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    code: str
    title: str
    description: str
    stars: int
    subscription_period: int | None = None


PRODUCTS = {
    "premium_monthly": Product(
        code="premium_monthly",
        title="FreXo Premium",
        description=(
            "Premium por 30 días: filtros avanzados, prioridad, "
            "perfiles ampliados y Likes recibidos."
        ),
        stars=199,
        subscription_period=2_592_000,
    ),
    "boost_30m": Product(
        code="boost_30m",
        title="Boost de 30 minutos",
        description="Aumenta tu prioridad de matchmaking durante 30 minutos.",
        stars=25,
    ),
    "boost_60m": Product(
        code="boost_60m",
        title="Boost de 60 minutos",
        description="Aumenta tu prioridad de matchmaking durante 60 minutos.",
        stars=45,
    ),
    "super_interest": Product(
        code="super_interest",
        title="Super Interés",
        description="Añade 1 Super Interés a tu saldo.",
        stars=10,
    ),
    "reconnect": Product(
        code="reconnect",
        title="Reconectar",
        description="Añade 1 intento de reconexión a tu saldo.",
        stars=15,
    ),
    "travel_24h": Product(
        code="travel_24h",
        title="Travel Pass 24 horas",
        description="Busca personas de un país específico durante 24 horas.",
        stars=15,
    ),
    "spotlight_3h": Product(
        code="spotlight_3h",
        title="Spotlight 3 horas",
        description="Destaca tu perfil en el matchmaking durante 3 horas.",
        stars=50,
    ),
    "gift_rose": Product(
        code="gift_rose",
        title="Rosa virtual",
        description="Envía una rosa virtual a tu conexión.",
        stars=5,
    ),
    "gift_coffee": Product(
        code="gift_coffee",
        title="Café virtual",
        description="Envía un café virtual a tu conexión.",
        stars=10,
    ),
    "gift_flowers": Product(
        code="gift_flowers",
        title="Flores virtuales",
        description="Envía flores virtuales a tu conexión.",
        stars=25,
    ),
    "gift_diamond": Product(
        code="gift_diamond",
        title="Diamante virtual",
        description="Envía un diamante virtual a tu conexión.",
        stars=100,
    ),
}
