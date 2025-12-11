"""Глобальный перехват и логирование ошибок."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger

from bot.utils.i18n import get_i18n

i18n = get_i18n()


class ErrorsMiddleware(BaseMiddleware):
    """Логирует исключения и уведомляет пользователя на его языке."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:  # noqa: BLE001
            locale = data.get("locale") or "ru"
            logger.exception("Ошибка при обработке апдейта: {error}", error=exc)
            text = data.get("gettext", lambda key, **kw: i18n.gettext(key, locale=locale))(
                "error_generic"
            )
            await self._notify(event, text)
            return None

    @staticmethod
    async def _notify(event: TelegramObject, text: str) -> None:
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(text)
            await event.answer()


__all__ = ["ErrorsMiddleware"]




