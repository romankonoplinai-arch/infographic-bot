import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # xAI Grok 4
    grok_api_key: str = os.getenv("GROK_API_KEY", "")
    grok_api_url: str = "https://api.x.ai/v1/chat/completions"
    grok_model: str = "grok-4"  # Grok 4 for SEO and keywords

    # OpenRouter (Nano Banana Pro)
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    nanobanana_model: str = "google/gemini-exp-1206"  # Nano Banana Pro (Gemini 3 Pro Image Preview)

    # Image settings
    max_image_size_mb: int = 10
    image_timeout_seconds: int = 120
    default_slides_count: int = 5
    min_slides: int = 3
    max_slides: int = 7

    # Marketplace image dimensions (WB/Ozon optimal)
    image_width: int = 900
    image_height: int = 1200


config = Config()


# Validate required config
def validate_config():
    errors = []
    if not config.telegram_bot_token or config.telegram_bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not config.grok_api_key:
        errors.append("GROK_API_KEY is not set")
    if not config.openrouter_api_key:
        errors.append("OPENROUTER_API_KEY is not set")

    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    return True
