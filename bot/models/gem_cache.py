"""Кеш отчётов безопасности и сигналов."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel

from .base import TimeStampedModel


class GemCache(TimeStampedModel, table=True):
    __tablename__ = "gem_cache"

    id: Optional[int] = Field(default=None, primary_key=True)
    token_address: str = Field(max_length=128, unique=True, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    score: float = Field(default=0.0)
    liquidity_usd: float = Field(default=0.0)
    volume_5m_usd: float = Field(default=0.0)


__all__ = ["GemCache"]




