import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config, validate_config
from bot.handlers import start, edit_photo, keywords, seo_slides, first_slide, slides_from_ref, free_image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def main():
    # Validate configuration
    if not validate_config():
        logger.error("Invalid configuration. Please check your .env file.")
        sys.exit(1)

    # Initialize bot and dispatcher
    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers
    dp.include_router(start.router)
    dp.include_router(edit_photo.router)
    dp.include_router(keywords.router)
    dp.include_router(seo_slides.router)
    dp.include_router(first_slide.router)
    dp.include_router(slides_from_ref.router)
    dp.include_router(free_image.router)

    # Start polling
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
