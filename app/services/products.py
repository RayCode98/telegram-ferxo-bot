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
            "Premium por 30 días: búsquedas ampliadas, prioridad y "
            "funciones avanzadas. Renovación cada 30 días."
        ),
        stars=199,
        subscription_period=2_592_000,
    ),
    "boost_30m": Product(
        code="boost_30m",
        title="Boost de 30 minutos",
        description="Aumenta temporalmente tu prioridad en el matchmaking.",
        stars=25,
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
}
