"""Регистрация всех роутеров Aiogram."""

from __future__ import annotations

from aiogram import Dispatcher


def register_routers(dispatcher: Dispatcher) -> None:
    """Подключает все доступные роутеры к диспетчеру."""

    from .core import common, referral, wallet
    from .ton import gem_hunter, positions, token_check, trading

    routers = (
        common.router,
        referral.router,
        wallet.router,
        gem_hunter.router,
        positions.router,
        token_check.router,
        trading.router,
    )

    for router in routers:
        dispatcher.include_router(router)


__all__ = ["register_routers"]


