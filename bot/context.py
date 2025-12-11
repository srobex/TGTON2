"""Глобальные сервисы и зависимости HyperSniper."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import get_settings
from .middlewares import get_session_maker
from .services.core.referral_service import ReferralService
from .services.core.ton_connect import TonConnectService
from .services.ton.gem_scanner import GemScanner
from .services.ton.gem_watch import GemWatchService
from .services.ton.price_feed import PriceFeedService
from .services.ton.safety_checker import SafetyChecker
from .services.ton.swap_service import SwapService
from .utils.cache import configure_cache
from .utils.i18n import get_i18n

settings = get_settings()

configure_cache()
session_maker = get_session_maker()

bot = Bot(
    token=settings.telegram.token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())

safety_checker = SafetyChecker()
gem_scanner = GemScanner(safety_checker=safety_checker)
swap_service = SwapService()
ton_connect = TonConnectService()
referral_service = ReferralService()
gem_watch_service = GemWatchService(bot)
i18n = get_i18n()
price_feed_service = PriceFeedService(swap_service.list_tracked_jettons)

swap_service.set_session_maker(session_maker)
ton_connect.set_session_maker(session_maker)
gem_scanner.set_session_maker(session_maker)

__all__ = [
    "bot",
    "dp",
    "gem_scanner",
    "gem_watch_service",
    "i18n",
    "price_feed_service",
    "referral_service",
    "safety_checker",
    "session_maker",
    "settings",
    "swap_service",
    "ton_connect",
]




