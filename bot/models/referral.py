"""Таблица реферальных связей."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimeStampedModel


class ReferralLink(TimeStampedModel, table=True):
    __tablename__ = "referrals"

    id: Optional[int] = Field(default=None, primary_key=True)
    referrer_id: int = Field(foreign_key="users.id", index=True)
    invitee_id: int = Field(foreign_key="users.id", unique=True, index=True)
    reward_usd: float = Field(default=0.0)
    volume_usd: float = Field(default=0.0)


__all__ = ["ReferralLink"]




