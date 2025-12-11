"""Заготовка Solana-плагина."""

from __future__ import annotations

from loguru import logger


def init_plugin(context: dict) -> None:
    dp = context["dp"]
    logger.info("Solana плагин подключён (заглушка)")
    # Здесь можно dp.include_router(...) и регистрировать сервисы


__all__ = ["init_plugin"]




