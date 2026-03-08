import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Configuration loaded from environment variables."""

    news_api_key: str | None
    news_api_base_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    min_move_percent: float
    max_move_percent: float
    max_movers_per_side: int


def load_settings() -> Settings:
    """Load configuration from environment variables with sensible defaults."""
    return Settings(
        news_api_key=os.getenv("NEWS_API_KEY"),
        news_api_base_url=os.getenv(
            "NEWS_API_BASE_URL",
            "https://api.marketaux.com/v1/news/all",
        ),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        min_move_percent=float(os.getenv("MIN_MOVE_PERCENT", "5")),
        max_move_percent=float(os.getenv("MAX_MOVE_PERCENT", "10")),
        max_movers_per_side=int(os.getenv("MAX_MOVERS_PER_SIDE", "30")),
    )
