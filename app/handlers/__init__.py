from app.handlers.admin import router as admin_router
from app.handlers.start import router as start_router
from app.handlers.profile import router as profile_router
from app.handlers.matchmaking import router as matchmaking_router
from app.handlers.payments import router as payments_router
from app.handlers.moderation import router as moderation_router
from app.handlers.social import router as social_router
from app.handlers.chat import router as chat_router

__all__ = [
    "admin_router",
    "start_router",
    "profile_router",
    "matchmaking_router",
    "payments_router",
    "moderation_router",
    "social_router",
    "chat_router",
]
