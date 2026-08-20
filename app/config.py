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
