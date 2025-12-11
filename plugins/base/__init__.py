"""Заготовка Base-плагина."""

from __future__ import annotations

from loguru import logger


def init_plugin(context: dict) -> None:
    logger.info("Base плагин подключён (заглушка)")


__all__ = ["init_plugin"]




