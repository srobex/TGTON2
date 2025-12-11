"""Поток цен для Jetton (используется авто-триггерами и P&L)."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import aiohttp
from loguru import logger

from config.settings import get_settings

PriceCallback = Callable[[str, float], Awaitable[None]]


class PriceFeedService:
    """Получает цены jetton через внешний API (tonapi совместимый)."""

    def __init__(self, get_tokens: Callable[[], Awaitable[set[str]]]) -> None:
        settings = get_settings().price_feed
        self._interval = settings.interval_sec
        self._source_url = str(settings.source_url)
        self._timeout = settings.request_timeout
        self._callbacks: set[PriceCallback] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._get_tokens = get_tokens

    def subscribe(self, callback: PriceCallback) -> None:
        self._callbacks.add(callback)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop(), name="price-feed-loop")
        logger.info("PriceFeedService запущен")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()

    async def _run_loop(self) -> None:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
            while not self._stop.is_set():
                tokens = await self._get_tokens()
                if tokens and self._callbacks:
                    await self._fetch_and_dispatch(session, tokens)
                await asyncio.sleep(self._interval)

    async def _fetch_and_dispatch(self, session: aiohttp.ClientSession, tokens: set[str]) -> None:
        chunk = list(tokens)
        query = ",".join(chunk)
        url = f"{self._source_url}{query}"
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.debug("PriceFeed ошибка HTTP {status}", status=resp.status)
                    return
                data = await resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("PriceFeed запрос упал: {error}", error=exc)
            return
        rates = self._parse_rates(data)
        if not rates:
            return
        await asyncio.gather(*(cb(token, price) for token, price in rates.items() for cb in self._callbacks))

    def _parse_rates(self, data) -> dict[str, float]:
        rates: dict[str, float] = {}
        items = data.get("rates") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return rates
        for item in items:
            token = item.get("token")
            price = item.get("prices", {}).get("usd")
            if token and isinstance(price, (int, float)):
                rates[token] = float(price)
        return rates


__all__ = ["PriceFeedService", "PriceCallback"]

