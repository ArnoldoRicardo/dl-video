from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TOKEN: str = "DUMMY_TOKEN"
    DATABASE_URL: str = "sqlite+aiosqlite:///data/bot.db"

    # Tier limits
    FREE_DAILY_LIMIT: int = 3
    PREMIUM_PRICE_STARS: int = 250
    PREMIUM_DURATION_DAYS: int = 30

    # Concurrency limits
    MAX_CONCURRENT_DOWNLOADS: int = 5
    MAX_DOWNLOADS_PER_USER: int = 1

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
