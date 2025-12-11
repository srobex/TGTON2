"""Сервис быстрой покупки/продажи и авто-менеджмента позиций."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import PositionStatus
from bot.repositories import (
    get_positions_by_jetton,
    load_active_rules,
    mark_rule_status,
    update_pnl,
    upsert_rule,
)
from config.settings import get_settings
from .ton_direct import TonDirectClient, get_ton_client


@dataclass(slots=True)
class SwapQuote:
    """Результат подготовки сделки."""

    tx_boc: str
    min_receive: float
    estimated_receive: float
    fee_nano: int
    referral_payload: str | None


@dataclass(slots=True)
class TakeProfitRule:
    """Автоматическая продажа позиции."""

    position_id: str
    user_id: int
    wallet: str
    jetton: str
    trigger_price_usd: float
    stop_price_usd: float | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SwapService:
    """Не кастодиальный уровень сделок HyperSniper."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._ton_settings = cfg.ton
        self._referral = cfg.referral
        self._ton_client: TonDirectClient | None = None
        self._rules: dict[str, TakeProfitRule] = {}
        self._listeners: set[Callable[[TakeProfitRule], Awaitable[None]]] = set()
        self._lock = asyncio.Lock()
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    async def prepare_buy(
        self,
        wallet: str,
        jetton: str,
        amount_ton: float,
        slippage_percent: float,
    ) -> SwapQuote:
        """Формирует non-custodial покупку jetton."""

        ton_client = await self._ensure_client()
        payload = self._build_payload(
            action="BUY",
            wallet=wallet,
            jetton=jetton,
            amount=amount_ton,
            slippage=slippage_percent,
        )
        fee = await ton_client.estimate_fee(payload)
        estimated_receive = amount_ton * 0.97  # грубая оценка
        min_receive = estimated_receive * (1 - slippage_percent / 100)
        return SwapQuote(
            tx_boc=payload,
            min_receive=min_receive,
            estimated_receive=estimated_receive,
            fee_nano=int(fee.get("source_fees", {}).get("fee", 0)),
            referral_payload=self._referral.omniston_payload,
        )

    async def prepare_sell(
        self,
        wallet: str,
        jetton: str,
        amount_jetton: float,
        slippage_percent: float,
    ) -> SwapQuote:
        """Формирует non-custodial продажу jetton."""

        ton_client = await self._ensure_client()
        payload = self._build_payload(
            action="SELL",
            wallet=wallet,
            jetton=jetton,
            amount=amount_jetton,
            slippage=slippage_percent,
        )
        fee = await ton_client.estimate_fee(payload)
        estimated_receive = amount_jetton * 0.95
        min_receive = estimated_receive * (1 - slippage_percent / 100)
        return SwapQuote(
            tx_boc=payload,
            min_receive=min_receive,
            estimated_receive=estimated_receive,
            fee_nano=int(fee.get("source_fees", {}).get("fee", 0)),
            referral_payload=self._referral.omniston_payload,
        )

    def set_session_maker(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    async def preload_rules(self) -> None:
        if self._session_maker is None:
            return
        async with self._session_maker() as session:
            positions = await load_active_rules(session)
        async with self._lock:
            self._rules = {
                pos.position_uid: TakeProfitRule(
                    position_id=pos.position_uid,
                    user_id=pos.user_id,
                    wallet=pos.wallet_address,
                    jetton=pos.jetton_address,
                    trigger_price_usd=pos.take_profit_usd,
                    stop_price_usd=pos.stop_loss_usd,
                    created_at=pos.created_at,
                )
                for pos in positions
            }

    async def register_take_profit(
        self,
        session: AsyncSession,
        *,
        position_id: str,
        user_id: int,
        wallet: str,
        jetton: str,
        trigger_price_usd: float,
        stop_price_usd: float | None = None,
    ) -> None:
        """Добавляет правило автопродажи."""

        rule = TakeProfitRule(
            position_id=position_id,
            user_id=user_id,
            wallet=wallet,
            jetton=jetton,
            trigger_price_usd=trigger_price_usd,
            stop_price_usd=stop_price_usd,
        )
        async with self._lock:
            self._rules[position_id] = rule
        await upsert_rule(
            session,
            position_uid=position_id,
            user_id=user_id,
            wallet=wallet,
            jetton=jetton,
            trigger_price_usd=trigger_price_usd,
            stop_price_usd=stop_price_usd,
        )
        logger.info(
            "Добавлено правило take-profit {pos}: tp={tp} stop={stop}",
            pos=position_id,
            tp=trigger_price_usd,
            stop=stop_price_usd,
        )

    async def remove_rule(self, session: AsyncSession, position_id: str) -> None:
        async with self._lock:
            self._rules.pop(position_id, None)
        await mark_rule_status(
            session,
            position_uid=position_id,
            status=PositionStatus.CLOSED,
        )

    def subscribe_auto_sell(self, callback: Callable[[TakeProfitRule], Awaitable[None]]) -> None:
        """Подписка на события автопродажи (бот шлёт уведомления)."""

        self._listeners.add(callback)

    async def on_price_update(self, position_id: str, price_usd: float) -> None:
        """Вызывается сервисом позиций при появлении нового прайс-типа."""

        rule = self._rules.get(position_id)
        if not rule:
            return
        if price_usd >= rule.trigger_price_usd or (
            rule.stop_price_usd is not None and price_usd <= rule.stop_price_usd
        ):
            await self._emit_auto_sell(rule)
            if self._session_maker:
                async with self._session_maker() as session:
                    await mark_rule_status(
                        session,
                        position_uid=position_id,
                        status=PositionStatus.AUTO_SOLD,
                    )
            async with self._lock:
                self._rules.pop(position_id, None)

    async def _emit_auto_sell(self, rule: TakeProfitRule) -> None:
        """Генерирует событие для подписчиков и логирует."""

        logger.info(
            "Срабатывание auto-sell {pos} ({jetton})",
            pos=rule.position_id,
            jetton=rule.jetton,
        )
        if not self._listeners:
            return
        await asyncio.gather(*(cb(rule) for cb in self._listeners))

    async def handle_price_update(self, jetton: str, price_usd: float) -> None:
        """Глобальный апдейт цены (используется PriceFeedService)."""

        async with self._lock:
            candidates = [rule for rule in self._rules.values() if rule.jetton == jetton]
        for rule in candidates:
            await self.on_price_update(rule.position_id, price_usd)

        if self._session_maker:
            async with self._session_maker() as session:
                positions = await get_positions_by_jetton(session, jetton)
                for pos in positions:
                    pnl_amount = pos.amount_jetton
                    if pnl_amount:
                        await update_pnl(
                            session,
                            position_uid=pos.position_uid,
                            amount_jetton=pnl_amount,
                            price_usd=price_usd,
                        )

    async def list_tracked_jettons(self) -> set[str]:
        async with self._lock:
            jettons = {rule.jetton for rule in self._rules.values()}
        return jettons

    async def _ensure_client(self) -> TonDirectClient:
        if self._ton_client is None:
            self._ton_client = await get_ton_client()
        return self._ton_client

    def _build_payload(self, **kwargs: Any) -> str:
        """Генерирует payload в base64 (готов к tonsdk)."""

        import base64
        import json

        data = {
            "action": kwargs["action"],
            "wallet": kwargs["wallet"],
            "jetton": kwargs["jetton"],
            "amount": kwargs["amount"],
            "slippage": kwargs["slippage"],
            "referral_payload": self._referral.omniston_payload,
        }
        return base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")


__all__ = ["SwapService", "SwapQuote", "TakeProfitRule"]

