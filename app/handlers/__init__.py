from app.handlers.support import router as support_router
from app.handlers.stats import router as personal_stats_router
from app.handlers.weekly import router as weekly_router
from app.handlers.feedback import router as feedback_router
from app.handlers.admin import router as admin_router
from app.handlers.start import router as start_router
from app.handlers.navigation import router as navigation_router
from app.handlers.chat_actions import router as chat_actions_router
from app.handlers.profile import router as profile_router
from app.handlers.interests import router as interests_router
from app.handlers.growth import router as growth_router
from app.handlers.gifts import router as gifts_router
from app.handlers.matchmaking import router as matchmaking_router
from app.handlers.notifications import router as notifications_router
from app.handlers.history import router as history_router
from app.handlers.payments import router as payments_router
from app.handlers.moderation import router as moderation_router
from app.handlers.social import router as social_router
from app.handlers.chat import router as chat_router

__all__ = [
    "support_router",
    "personal_stats_router",
    "weekly_router",
    "feedback_router",
    "admin_router", "start_router", "navigation_router", "chat_actions_router",
    "profile_router", "interests_router", "growth_router", "gifts_router",
    "matchmaking_router", "notifications_router", "history_router",
    "payments_router", "moderation_router", "social_router", "chat_router",
]
