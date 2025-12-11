"""Middleware мультиязычности."""

from __future__ import annotations

from functools import partial
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.utils.i18n import get_i18n

i18n = get_i18n()


class I18nMiddleware(BaseMiddleware):
    """Определяет язык пользователя и подставляет gettext в контекст."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        language_code = getattr(user, "language_code", None) if user else None
        locale = i18n.detect_locale(language_code)
        data["locale"] = locale
        data["gettext"] = partial(i18n.gettext, locale=locale)
        return await handler(event, data)


__all__ = ["I18nMiddleware"]




