"""Настройка loguru для продакшена."""

from __future__ import annotations

import sys
from loguru import logger


def setup_logging(json: bool = False) -> None:
    logger.remove()
    fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    if json:
        fmt = (
            "{{\"time\":\"{time:YYYY-MM-DDTHH:mm:ss}\","
            "\"level\":\"{level}\","
            "\"message\":{message},"
            "\"extra\":{extra}}}"
        )
    logger.add(
        sys.stdout,
        format=fmt,
        level="DEBUG",
        colorize=not json,
        backtrace=False,
        enqueue=True,
    )


__all__ = ["setup_logging"]




