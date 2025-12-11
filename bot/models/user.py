"""SQLModel модель пользователя."""

from __future__ import annotations

import secrets
from typing import Optional

from sqlmodel import Field

from .base import TimeStampedModel



class User(TimeStampedModel, table=True):
    """Основная запись пользователя HyperSniper."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(index=True, unique=True)
    username: Optional[str] = Field(default=None, max_length=64)
    language: str = Field(default="auto", max_length=8)
    wallet_address: Optional[str] = Field(default=None, max_length=128, index=True)
    public_key: Optional[str] = Field(default=None, max_length=256)
    device: Optional[str] = Field(default=None, max_length=64)
    referral_code: str = Field(
        default_factory=lambda: secrets.token_hex(4),
        max_length=32,
        index=True,
        unique=True,
    )

__all__ = ["User"]

