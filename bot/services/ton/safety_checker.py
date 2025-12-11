"""Safety Checker HyperSniper.

Проверяет jetton на honeypot, владельцев, ликвидность и активность смарт-кошельков.
Цель — выдавать вердикт < 600 мс и отбрасывать токсичные токены до попадания в Gem Hunter.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from config.settings import get_settings
from bot.utils.cache import get_cache
from .ton_direct import TonDirectClient, get_ton_client


@dataclass(slots=True)
class SafetyReport:
    """Результат проверки токена."""

    is_safe: bool
    score: float
    reasons: tuple[str, ...]
    liquidity_usd: float
    volume_5m_usd: float
    smart_money_hits: int
    lp_burned: bool
    is_new: bool
    owner: str | None


class SafetyChecker:
    """Высокоскоростной слой защиты трейдеров."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._security = cfg.ton_security
        self._cache = get_cache()
        self._cache_ttl = cfg.cache.ttl_seconds
        self._ton_client: TonDirectClient | None = None
        self._timeout = self._security.max_safety_latency_ms / 1000

    async def check_jetton(
        self,
        address: str,
        raw_event: dict[str, Any] | None = None,
    ) -> SafetyReport:
        """Возвращает SafetyReport из кеша либо выполняет быструю проверку."""

        cached = await self._cache.get(address)
        if cached:
            return cached
        ton_client = await self._ensure_client()
        report = await asyncio.wait_for(
            self._run_pipeline(ton_client, address, raw_event or {}),
            timeout=self._timeout,
        )
        await self._cache.set(address, report, ttl=self._cache_ttl)
        return report

    async def _run_pipeline(
        self,
        ton_client: TonDirectClient,
        address: str,
        raw_event: dict[str, Any],
    ) -> SafetyReport:
        """Основные проверки выполняются параллельно."""

        jetton_data = await ton_client.get_jetton_data(address)
        results = await asyncio.gather(
            self._simulate_honeypot(ton_client, address, raw_event),
            self._calc_liquidity(jetton_data, raw_event),
            self._calc_volume(raw_event),
            self._check_smart_money(raw_event),
            return_exceptions=True,
        )
        honeypot_allowed = self._unwrap(results[0], True)
        liquidity = self._unwrap(results[1], 0.0)
        volume = self._unwrap(results[2], 0.0)
        smart_money_hits = self._unwrap(results[3], 0)
        owner = jetton_data.get("admin_address") or raw_event.get("owner")
        lp_burned = bool(
            jetton_data.get("lp_status") == "burned"
            or raw_event.get("lp_burned")
            or not owner
        )
        is_new = self._is_new_token(raw_event)
        score, reasons = self._score_token(
            honeypot_allowed=honeypot_allowed,
            owner=owner,
            liquidity=liquidity,
            volume=volume,
            smart_money_hits=smart_money_hits,
            lp_burned=lp_burned,
            is_new=is_new,
        )
        return SafetyReport(
            is_safe=score >= 70 and honeypot_allowed,
            score=score,
            reasons=tuple(reasons),
            liquidity_usd=liquidity,
            volume_5m_usd=volume,
            smart_money_hits=smart_money_hits,
            lp_burned=lp_burned,
            is_new=is_new,
            owner=owner,
        )

    async def _simulate_honeypot(
        self,
        ton_client: TonDirectClient,
        address: str,
        raw_event: dict[str, Any],
    ) -> bool:
        """Проверка honeypot через simulateMessageProcess."""

        boc = raw_event.get("simulate_boc")
        if not boc:
            return True
        try:
            result = await ton_client.simulate_tx(boc, address)
        except Exception as exc:  # noqa: BLE001
            logger.debug("simulate_tx {addr} упал: {error}", addr=address, error=exc)
            return False
        return bool(result.get("success", True))

    async def _calc_liquidity(
        self,
        jetton_data: dict[str, Any],
        raw_event: dict[str, Any],
    ) -> float:
        """Оценка ликвидности в USD."""

        liquidity = (
            jetton_data.get("liquidity_usd")
            or raw_event.get("liquidity_usd")
            or raw_event.get("pool_stats", {}).get("liquidity_usd")
        )
        try:
            return float(liquidity or 0.0)
        except (TypeError, ValueError):
            return 0.0

    async def _calc_volume(self, raw_event: dict[str, Any]) -> float:
        """Оборот за последние 5 минут."""

        volume = raw_event.get("volume_5m_usd") or raw_event.get("volume_usd")
        try:
            return float(volume or 0.0)
        except (TypeError, ValueError):
            return 0.0

    async def _check_smart_money(self, raw_event: dict[str, Any]) -> int:
        """Количество входов смарт-кошельков в пул."""

        addresses = set(raw_event.get("holders", [])) | set(raw_event.get("buyers", []))
        trusted = set(self._security.trusted_smart_money)
        return len(addresses & trusted)

    def _is_new_token(self, raw_event: dict[str, Any]) -> bool:
        """Jetton считается новым, если ему < 2 часов."""

        ts = raw_event.get("timestamp")
        if not ts:
            return False
        created = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() < 7200

    def _score_token(
        self,
        *,
        honeypot_allowed: bool,
        owner: str | None,
        liquidity: float,
        volume: float,
        smart_money_hits: int,
        lp_burned: bool,
        is_new: bool,
    ) -> tuple[float, list[str]]:
        """Формула скоринга (0-100)."""

        score = 60.0
        reasons: list[str] = []
        if not honeypot_allowed:
            score -= 40
            reasons.append("simulate_tx заблокировал транзакцию")
        if owner and owner in self._security.blacklist_addresses:
            reasons.append("адрес владельца в чёрном списке")
            return 0.0, reasons
        if not owner:
            score += 8
            reasons.append("адрес владельца не найден — возможный burn")
        if liquidity < self._security.min_liquidity_usd:
            score -= 10
            reasons.append("низкая ликвидность")
        else:
            score += min(liquidity / 1_000, 10)
        if volume < self._security.min_volume_5m_usd:
            score -= 5
        else:
            score += min(volume / 2_000, 15)
        score += smart_money_hits * 4
        if lp_burned:
            score += 5
            reasons.append("LP burned")
        if is_new:
            score += 3
        score = max(0.0, min(score, 100.0))
        return score, reasons

    async def _ensure_client(self) -> TonDirectClient:
        if self._ton_client is None:
            self._ton_client = await get_ton_client()
        return self._ton_client

    @staticmethod
    def _unwrap(value: Any, fallback: Any) -> Any:
        if isinstance(value, Exception):
            logger.debug(
                "SafetyChecker подзадача завершилась ошибкой: {error}",
                error=value,
            )
            return fallback
        return value


__all__ = ["SafetyChecker", "SafetyReport"]

