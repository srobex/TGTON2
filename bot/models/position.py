"""Хранение позиций пользователя."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimeStampedModel


class PositionStatus(str):
    OPEN = "open"
    CLOSED = "closed"
    AUTO_SOLD = "auto_sold"


class Position(TimeStampedModel, table=True):
    __tablename__ = "positions"

    id: Optional[int] = Field(default=None, primary_key=True)
    position_uid: str = Field(default_factory=lambda: "", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    wallet_address: str = Field(max_length=128, index=True)
    jetton_address: str = Field(max_length=128, index=True)
    amount_jetton: float = Field(default=0.0)
    avg_price_usd: float = Field(default=0.0)
    take_profit_usd: Optional[float] = Field(default=None)
    stop_loss_usd: Optional[float] = Field(default=None)
    status: str = Field(default=PositionStatus.OPEN, index=True)


__all__ = ["Position", "PositionStatus"]




