import asyncio
import logging
import sys
import uvloop
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.config import BotConfig
from src.bot.routers import base

async def main():
    # Load config
    config = BotConfig()
    
    # Initialize Bot
    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize Dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    
    from src.bot.routers import base, content, worker_cmds
    
    # Register routers
    dp.include_router(base.router)
    dp.include_router(content.router)
    dp.include_router(worker_cmds.router)
    
    # Inject config into middleware/workflow data
    dp["config"] = config
    
    # Delete webhook and start polling
    logger.info("🚀 Starting SecBrain Bot (Aiogram 3.x)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Install uvloop policy
    if sys.platform != "win32":
        uvloop.install()
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped!")
