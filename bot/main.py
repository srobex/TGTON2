"""Entry point for HyperSniper bot."""

from __future__ import annotations

import asyncio

from aiogram import Dispatcher
from loguru import logger

from .loader import bot, dp, on_shutdown, on_startup
from .logging_config import setup_logging


async def main() -> None:
    setup_logging()
    logger.info("Запуск aiogram polling...")
    await on_startup(dp)
    await dp.start_polling(bot)
    await on_shutdown(dp)
    logger.info("Polling завершён (dp.start_polling вернул управление)")


if __name__ == "__main__":
    asyncio.run(main())




