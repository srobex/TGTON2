"""Loader HyperSniper — ядро инициализации всех модулей."""

from __future__ import annotations

import asyncio

from aiogram import Dispatcher
from loguru import logger

from .context import (
    bot,
    dp,
    gem_scanner,
    gem_watch_service,
    i18n,
    price_feed_service,
    referral_service,
    safety_checker,
    settings,
    swap_service,
    ton_connect,
)
from .handlers import register_routers
from .middlewares import (
    DatabaseMiddleware,
    ErrorsMiddleware,
    I18nMiddleware,
    ThrottlingMiddleware,
)
from .services.ton.ton_direct import get_ton_client
from .utils.plugins_loader import load_chain_plugins

_loaded_plugins: list[str] = []

register_routers(dp)


async def on_startup(dispatcher: Dispatcher) -> None:
    """Регистрация middlewares, запуск фоновых задач."""

    logger.info("HyperSniper стартует в окружении {env}", env=settings.environment)
    logger.debug("on_startup: preload ton_connect wallets")
    await ton_connect.preload_wallets()
    logger.debug("on_startup: preload swap rules")
    await swap_service.preload_rules()
    logger.debug("on_startup: subscribe price feed service")
    price_feed_service.subscribe(_price_feed_dispatch)
    logger.debug("on_startup: start price feed")
    await price_feed_service.start()
    logger.debug("on_startup: set bot for gem scanner notifications")
    gem_scanner.set_bot(bot)
    logger.debug("on_startup: start gem scanner")
    await gem_scanner.start()
    logger.debug("on_startup: setup middlewares")
    await _setup_middlewares(dispatcher)
    logger.debug("on_startup: load plugins")
    _load_plugins()
    logger.debug("on_startup: attach gem scanner subscribers")
    gem_scanner.subscribe(_log_hot_tokens)
    gem_scanner.subscribe(gem_watch_service.handle_signals)
    swap_service.subscribe_auto_sell(_notify_auto_sell)
    logger.info("on_startup завершён, бот готов принимать апдейты")


async def on_shutdown(dispatcher: Dispatcher) -> None:
    """Мягкое выключение сервиса."""

    await gem_scanner.stop()
    await price_feed_service.stop()
    ton_client = await get_ton_client()
    await ton_client.close()
    logger.info("HyperSniper корректно остановлен")


async def _log_hot_tokens(signals) -> None:
    """Простейший подписчик GemScanner (логирует, пока нет UI)."""

    if not signals:
        return
    top = ", ".join(f"{sig.symbol or sig.address}:{sig.score:.1f}" for sig in signals)
    logger.debug("Актуальный топ Gem Hunter: {hot}", hot=top)


async def _setup_middlewares(dispatcher: Dispatcher) -> None:
    """Подключает i18n/throttling/DB/error middlewares."""

    i18n_mw = I18nMiddleware()
    throttling_mw = ThrottlingMiddleware(rate_limit=0.5)
    db_mw = DatabaseMiddleware()
    errors_mw = ErrorsMiddleware()

    dispatcher.message.middleware(i18n_mw)
    dispatcher.callback_query.middleware(i18n_mw)

    dispatcher.message.middleware(throttling_mw)
    dispatcher.callback_query.middleware(throttling_mw)

    dispatcher.message.middleware(db_mw)
    dispatcher.callback_query.middleware(db_mw)

    dispatcher.message.middleware(errors_mw)
    dispatcher.callback_query.middleware(errors_mw)

    logger.debug("Middleware стек активирован")


def _load_plugins() -> None:
    """Автоматически подключает цепочки из папки plugins/."""

    global _loaded_plugins
    if _loaded_plugins:
        return
    context = {
        "dp": dp,
        "bot": bot,
        "settings": settings,
        "services": {
            "safety_checker": safety_checker,
            "gem_scanner": gem_scanner,
            "swap_service": swap_service,
            "ton_connect": ton_connect,
        },
    }
    modules = load_chain_plugins(context=context)
    if not modules:
        logger.debug("Плагины не найдены — подключите цепи в каталоге plugins/")
        return
    _loaded_plugins = [module.__name__ for module in modules]
    logger.info("Подключены плагины: {plugins}", plugins=", ".join(_loaded_plugins))


async def _notify_auto_sell(rule) -> None:
    """Сообщает пользователю о сработавшем авто-селле."""

    user_id = await ton_connect.find_user_by_wallet(rule.wallet)
    if not user_id:
        return
    locale = i18n.default_locale
    text = i18n.gettext(
        "auto_sell_notice",
        locale=locale,
        position=rule.position_id,
        jetton=rule.jetton,
        tp=rule.trigger_price_usd,
        stop=rule.stop_price_usd or "-",
    )
    await bot.send_message(chat_id=user_id, text=text)


async def _price_feed_dispatch(token: str, price: float) -> None:
    await swap_service.handle_price_update(token, price)


__all__ = [
    "bot",
    "dp",
    "gem_scanner",
    "gem_watch_service",
    "on_shutdown",
    "on_startup",
    "referral_service",
    "safety_checker",
    "settings",
    "swap_service",
    "ton_connect",
]

