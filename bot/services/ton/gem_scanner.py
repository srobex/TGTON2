"""Alpha Scanner / Gem Hunter для HyperSniper.

Модуль отслеживает появление новых JettonMinter через TonDirectClient,
автоматически прогоняет их через SafetyChecker и формирует топ-10 горячих токенов.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence

import aiohttp
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.repositories import upsert_gem_cache
from bot.utils.cache import get_cache
from config.settings import get_settings
from .safety_checker import SafetyChecker, SafetyReport
from .ton_direct import JettonMinterEvent, get_ton_client


@dataclass(slots=True)
class GemSignal:
    """Описывает горячий токен для показа пользователям."""

    address: str
    symbol: str | None
    score: float
    tags: tuple[str, ...]
    report: SafetyReport
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, str | float | int | bool]:
        return {
            "address": self.address,
            "symbol": self.symbol or "???",
            "score": round(self.score, 2),
            "tags": self.tags,
            "liquidity_usd": self.report.liquidity_usd,
            "volume_5m_usd": self.report.volume_5m_usd,
            "smart_money": self.report.smart_money_hits,
            "lp_burned": self.report.lp_burned,
            "is_new": self.report.is_new,
        }


class GemScanner:
    """Главный сервис Alpha Scanner."""

    def __init__(self, safety_checker: SafetyChecker) -> None:
        self._settings = get_settings().gem_scanner
        self._safety_checker = safety_checker
        self._ton_client = None
        self._hot_tokens: list[GemSignal] = []
        self._lock = asyncio.Lock()
        self._subscribers: set[Callable[[Sequence[GemSignal]], Awaitable[None]]] = set()
        self._refresh_task: asyncio.Task[None] | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None
        self._cache = get_cache()
        self._filters: dict[str, Any] = {
            "min_score": 0.0,
            "lp_burned_only": False,
            "smart_money_min": 0,
            "sort_key": "score",
        }

    async def start(self) -> None:
        """Поднимает TonDirect и подписку на JettonMinter."""

        if self._ton_client is None:
            self._ton_client = await get_ton_client()
            self._ton_client.subscribe_jetton_minters(self._on_new_jetton)
            logger.info("GemScanner подписался на TonDirect JettonMinter поток")
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._periodic_push(), name="gem-hot-push")
            logger.debug("GemScanner фоновая задача refresh запущена (интервал %s c)", self._settings.refresh_interval_sec)
        logger.info("GemScanner активирован")

    async def stop(self) -> None:
        """Останавливает фоновые задачи (используется при graceful shutdown)."""

        if self._refresh_task:
            self._refresh_task.cancel()

    def subscribe(self, callback: Callable[[Sequence[GemSignal]], Awaitable[None]]) -> None:
        """Добавляет подписчика для топа (например, бродкаст хендлеру)."""

        self._subscribers.add(callback)

    async def get_top(self, limit: int = 10) -> list[GemSignal]:
        """Возвращает текущий топ в порядке убывания score."""

        async with self._lock:
            return self._apply_filters(self._hot_tokens)[:limit]

    async def _on_new_jetton(self, event: JettonMinterEvent) -> None:
        """Колбэк от TonDirect: прогоняем токен через фильтры."""

        report = await self._safety_checker.check_jetton(event.address, event.raw)
        if not report.is_safe:
            logger.debug("Jetton {addr} отклонён safety фильтром", addr=event.address)
            return
        if report.liquidity_usd < self._settings.min_liquidity_usd:
            logger.debug(
                "Jetton {addr} отклонён: ликвидность {liq} < {min_liq}",
                addr=event.address,
                liq=report.liquidity_usd,
                min_liq=self._settings.min_liquidity_usd,
            )
            return
        if report.volume_5m_usd < self._settings.min_volume_5m_usd:
            logger.debug(
                "Jetton {addr} отклонён: объём {vol} < {min_vol}",
                addr=event.address,
                vol=report.volume_5m_usd,
                min_vol=self._settings.min_volume_5m_usd,
            )
            return
        score = self._calc_score(report)
        async with self._lock:
            tags = self._build_tags(report)
            signal = GemSignal(
                address=event.address,
                symbol=event.symbol,
                score=score,
                tags=tags,
                report=report,
            )
            self._hot_tokens.append(signal)
            self._hot_tokens.sort(key=lambda x: x.score, reverse=True)
            self._hot_tokens = self._hot_tokens[: self._settings.burst_threshold_tokens]
        logger.info(
            "Новый сигнал GemHunter: {symbol} ({addr}) рейтинг {score:.1f}, ликвидность {liq}, объём {vol}",
            symbol=event.symbol or event.address[-6:],
            addr=event.address,
            score=score,
            liq=report.liquidity_usd,
            vol=report.volume_5m_usd,
        )
        await self._persist_signal(signal)

    async def _periodic_push(self) -> None:
        """Раз в refresh_interval_sec отправляет топ подписчикам."""

        interval = self._settings.refresh_interval_sec
        while True:
            await asyncio.sleep(interval)
            snapshot = await self.get_top(limit=10)
            await self._cache.set("gem:top", [sig.as_dict() for sig in snapshot], ttl=interval)
            if not snapshot:
                logger.debug("GemScanner refresh: топ пуст — ждём новые JettonMinter события")
                continue
            if not self._subscribers:
                logger.trace("GemScanner refresh: нет подписчиков, вебхуки и гл. рассылка пропущены")
                continue
            logger.debug(
                "GemScanner refresh: отправляем топ (%d токенов) %d подписчикам",
                len(snapshot),
                len(self._subscribers),
            )
            await asyncio.gather(*(self._safe_emit(cb, snapshot) for cb in self._subscribers))
            await self._push_webhooks(snapshot)

    async def _safe_emit(
        self,
        callback: Callable[[Sequence[GemSignal]], Awaitable[None]],
        payload: Sequence[GemSignal],
    ) -> None:
        try:
            await callback(payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Подписчик GemScanner упал: {error}", error=exc)

    def _calc_score(self, report: SafetyReport) -> float:
        """Считает итоговый рейтинг токена."""

        score = report.score
        score += min(report.liquidity_usd / 1_000, 40)
        score += min(report.volume_5m_usd / 2_000, 30)
        score += report.smart_money_hits * 5
        if report.lp_burned:
            score += 5
        if report.is_new:
            score += 3
        if report.is_safe and report.volume_5m_usd >= self._settings.min_volume_5m_usd * 2:
            score += 5
        return score

    def _build_tags(self, report: SafetyReport) -> tuple[str, ...]:
        """Формирует набор меток для UI."""

        tags: list[str] = []
        if report.smart_money_hits > 0:
            tags.append("Smart money inside")
        if report.lp_burned:
            tags.append("LP burned")
        if report.is_new:
            tags.append("New")
        return tuple(tags)

    def set_session_maker(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    async def _persist_signal(self, signal: GemSignal) -> None:
        if self._session_maker is None:
            return
        async with self._session_maker() as session:
            await upsert_gem_cache(session, signal)

    def set_filters(
        self,
        *,
        min_score: float,
        lp_burned_only: bool,
        smart_money_min: int,
        sort_key: str | None = None,
    ) -> None:
        self._filters["min_score"] = min_score
        self._filters["lp_burned_only"] = lp_burned_only
        self._filters["smart_money_min"] = smart_money_min
        if sort_key in {"score", "volume"}:
            self._filters["sort_key"] = sort_key

    def get_filters(self) -> dict[str, Any]:
        return dict(self._filters)

    def _apply_filters(self, tokens: list[GemSignal]) -> list[GemSignal]:
        filtered = []
        for token in tokens:
            if token.score < self._filters["min_score"]:
                continue
            if self._filters["lp_burned_only"] and not token.report.lp_burned:
                continue
            if token.report.smart_money_hits < self._filters["smart_money_min"]:
                continue
            filtered.append(token)
        sort_key = self._filters.get("sort_key", "score")
        if sort_key == "volume":
            filtered.sort(key=lambda token: token.report.volume_5m_usd, reverse=True)
        else:
            filtered.sort(key=lambda token: token.score, reverse=True)
        return filtered

    async def _push_webhooks(self, snapshot: Sequence[GemSignal]) -> None:
        from bot.web.webhooks import get_webhook_subscribers

        subscribers = get_webhook_subscribers()
        if not subscribers:
            return
        payload = {"tokens": [sig.as_dict() for sig in snapshot]}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
            await asyncio.gather(
                *(
                    self._post_webhook(session, sub.callback_url, payload)
                    for sub in subscribers.values()
                    if snapshot and snapshot[0].score >= sub.min_score
                )
            )

    async def _post_webhook(
        self,
        session: aiohttp.ClientSession,
        url: str,
        payload: dict,
    ) -> None:
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    logger.debug("Webhook {url} ответил статусом {status}", url=url, status=resp.status)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Webhook {url} не доступен: {error}", url=url, error=exc)


__all__ = ["GemScanner", "GemSignal"]

