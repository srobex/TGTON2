"""Работа с позициями и правилами auto-sell."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from bot.models import Position, PositionStatus


async def upsert_rule(
    session: AsyncSession,
    *,
    position_uid: str,
    user_id: int,
    wallet: str,
    jetton: str,
    trigger_price_usd: float,
    stop_price_usd: float | None = None,
) -> Position:
    stmt = select(Position).where(Position.position_uid == position_uid)
    position = (await session.exec(stmt)).one_or_none()
    if position is None:
        position = Position(
            position_uid=position_uid,
            user_id=user_id,
            wallet_address=wallet,
            jetton_address=jetton,
            take_profit_usd=trigger_price_usd,
            stop_loss_usd=stop_price_usd,
            status=PositionStatus.OPEN,
        )
    else:
        position.take_profit_usd = trigger_price_usd
        position.stop_loss_usd = stop_price_usd
        position.status = PositionStatus.OPEN
    session.add(position)
    await session.commit()
    await session.refresh(position)
    return position


async def list_rules_for_wallet(session: AsyncSession, wallet: str) -> Sequence[Position]:
    stmt = select(Position).where(
        Position.wallet_address == wallet,
        Position.status == PositionStatus.OPEN,
    )
    result = await session.exec(stmt)
    return result.all()


async def load_active_rules(session: AsyncSession) -> list[Position]:
    stmt = select(Position).where(Position.status == PositionStatus.OPEN)
    result = await session.exec(stmt)
    return list(result.all())


async def mark_rule_status(
    session: AsyncSession,
    *,
    position_uid: str,
    status: str,
) -> None:
    stmt = select(Position).where(Position.position_uid == position_uid)
    position = (await session.exec(stmt)).one_or_none()
    if position is None:
        return
    position.status = status
    session.add(position)
    await session.commit()


async def update_pnl(
    session: AsyncSession,
    *,
    position_uid: str,
    amount_jetton: float,
    price_usd: float,
) -> None:
    stmt = select(Position).where(Position.position_uid == position_uid)
    position = (await session.exec(stmt)).one_or_none()
    if position is None:
        return
    position.amount_jetton = amount_jetton
    position.avg_price_usd = price_usd
    session.add(position)
    await session.commit()


async def get_positions_by_jetton(session: AsyncSession, jetton: str) -> list[Position]:
    stmt = select(Position).where(
        Position.jetton_address == jetton,
        Position.status == PositionStatus.OPEN,
    )
    result = await session.exec(stmt)
    return list(result.all())


__all__ = [
    "get_positions_by_jetton",
    "list_rules_for_wallet",
    "load_active_rules",
    "mark_rule_status",
    "update_pnl",
    "upsert_rule",
]

