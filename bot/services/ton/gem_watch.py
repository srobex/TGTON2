"""Сервис подписок пользователей на сигналы Gem Hunter."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Sequence

from aiogram import Bot
from loguru import logger

from bot.keyboards.inline.gem import build_gem_list_keyboard, build_token_keyboard
from .gem_scanner import GemSignal


class GemWatchService:
    """Хранит подписки user_id -> token и рассылает уведомления."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._token_watchers: dict[str, set[int]] = defaultdict(set)
        self._user_watchlist: dict[int, set[str]] = defaultdict(set)
        self._global_watchers: set[int] = set()
        self._lock = asyncio.Lock()

    async def toggle_watch(self, user_id: int, token: str) -> bool:
        """Добавляет либо убирает токен из списка пользователя. Возвращает True, если подписка активна."""

        async with self._lock:
            if token in self._user_watchlist[user_id]:
                self._user_watchlist[user_id].remove(token)
                self._token_watchers[token].discard(user_id)
                if not self._token_watchers[token]:
                    self._token_watchers.pop(token, None)
                return False
            self._user_watchlist[user_id].add(token)
            self._token_watchers[token].add(user_id)
            return True

    async def subscribe_global(self, user_id: int) -> bool:
        async with self._lock:
            if user_id in self._global_watchers:
                return False
            self._global_watchers.add(user_id)
            return True

    async def unsubscribe_global(self, user_id: int) -> bool:
        async with self._lock:
            if user_id not in self._global_watchers:
                return False
            self._global_watchers.remove(user_id)
            return True

    async def list_tokens(self, user_id: int) -> list[str]:
        async with self._lock:
            return sorted(self._user_watchlist.get(user_id, set()))

    async def handle_signals(self, signals: Sequence[GemSignal]) -> None:
        """Получает снапшот топа и уведомляет всех подписчиков по их токенам."""

        if not signals:
            return

        notify_map: dict[int, list[GemSignal]] = {}
        async with self._lock:
            for signal in signals:
                watchers = self._token_watchers.get(signal.address)
                if not watchers:
                    continue
                for user_id in watchers:
                    notify_map.setdefault(user_id, []).append(signal)
            global_watchers = set(self._global_watchers)

        for user_id, user_signals in notify_map.items():
            keyboard = build_token_keyboard(user_signals[0].address)
            await self._safe_send(user_id, self._format_message(user_signals), keyboard)

        if global_watchers:
            broadcast_text = self._format_top(signals)
            keyboard = build_gem_list_keyboard()
            await asyncio.gather(*(self._safe_send(user_id, broadcast_text, keyboard) for user_id in global_watchers))

    async def _safe_send(self, user_id: int, text: str, keyboard=None) -> None:
        try:
            await self._bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
        except Exception as exc:  # noqa: BLE001
            logger.error("Не удалось отправить уведомление пользователю {user}: {error}", user=user_id, error=exc)

    @staticmethod
    def _format_message(signals: Sequence[GemSignal]) -> str:
        lines = ["🔥 Обновление по отслеживаемым токенам:"]
        for signal in signals:
            tags = ", ".join(signal.tags) if signal.tags else "меток нет"
            lines.append(
                f"{signal.symbol or signal.address[-6:]} • рейтинг {signal.score:.1f} • {tags}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_top(signals: Sequence[GemSignal]) -> str:
        lines = ["🔥 Топ HyperSniper (auto-feed):"]
        for idx, signal in enumerate(signals, start=1):
            tags = ", ".join(signal.tags) if signal.tags else "меток нет"
            lines.append(f"{idx}. {signal.symbol or signal.address[-6:]} • {signal.score:.1f} • {tags}")
        return "\n".join(lines)


__all__ = ["GemWatchService"]

