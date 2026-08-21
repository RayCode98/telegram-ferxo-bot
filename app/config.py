from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    redis_url: str

    support_username: str = "@TuSoporte"
    admin_ids: str = ""

    free_daily_search_limit: int = 30
    default_nearby_radius_km: int = 100

    # Seguridad / antiabuso
    chat_messages_limit: int = 8
    chat_messages_window_seconds: int = 5
    next_limit: int = 8
    next_window_seconds: int = 120
    search_burst_limit: int = 10
    search_burst_window_seconds: int = 60
    report_daily_limit: int = 5
    protect_relayed_content: bool = True

    # Calidad de conversación
    ghosting_nudge_minutes: int = 15
    conversation_idle_close_hours: int = 24
    consecutive_message_nudge: int = 4

    # Producción / health
    health_host: str = "0.0.0.0"
    health_port: int = 8080
    environment: str = "production"
    legal_effective_date: str = "21/08/2026"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admins(self) -> set[int]:
        if not self.admin_ids.strip():
            return set()
        return {
            int(item.strip())
            for item in self.admin_ids.split(",")
            if item.strip().isdigit()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
