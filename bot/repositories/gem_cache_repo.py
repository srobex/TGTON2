"""Работа с таблицей GemCache."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from bot.models import GemCache

if TYPE_CHECKING:
    from bot.services.ton.gem_scanner import GemSignal


async def upsert_gem_cache(session: AsyncSession, signal: "GemSignal") -> GemCache:
    stmt = select(GemCache).where(GemCache.token_address == signal.address)
    cache_entry = (await session.exec(stmt)).one_or_none()
    payload = signal.report.raw if hasattr(signal.report, "raw") else {}
    if cache_entry is None:
        cache_entry = GemCache(
            token_address=signal.address,
            payload=payload,
            score=signal.score,
            liquidity_usd=signal.report.liquidity_usd,
            volume_5m_usd=signal.report.volume_5m_usd,
        )
    else:
        cache_entry.payload = payload
        cache_entry.score = signal.score
        cache_entry.liquidity_usd = signal.report.liquidity_usd
        cache_entry.volume_5m_usd = signal.report.volume_5m_usd
    session.add(cache_entry)
    await session.commit()
    await session.refresh(cache_entry)
    return cache_entry


__all__ = ["upsert_gem_cache"]


