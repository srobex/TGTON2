"""SQLModel модель пользовательских настроек."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimeStampedModel


class UserSettings(TimeStampedModel, table=True):
    __tablename__ = "user_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    locale_preference: str = Field(default="auto", max_length=8)
    notifications_enabled: bool = Field(default=True)
    auto_take_profit: bool = Field(default=True)
    anti_rug_enabled: bool = Field(default=True)
    referral_payouts_enabled: bool = Field(default=True)

__all__ = ["UserSettings"]

