"""Простое антиспам middleware."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.utils.i18n import get_i18n

i18n = get_i18n()


class ThrottlingMiddleware(BaseMiddleware):
    """Ограничивает частоту команд от одного пользователя."""

    def __init__(self, rate_limit: float = 1.0) -> None:
        self.rate_limit = rate_limit
        self._timestamps: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        async with self._lock:
            now = time.monotonic()
            last = self._timestamps.get(user_id, 0.0)
            if now - last < self.rate_limit:
                await self._notify_throttled(event, data)
                return None
            self._timestamps[user_id] = now

        return await handler(event, data)

    async def _notify_throttled(self, event: TelegramObject, data: Dict[str, Any]) -> None:
        locale = data.get("locale") or "ru"
        message = data.get("gettext", lambda key, **kw: i18n.gettext(key, locale=locale))(
            "throttled"
        )
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=False)


__all__ = ["ThrottlingMiddleware"]




