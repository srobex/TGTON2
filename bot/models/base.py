"""Базовые примеси для SQLModel моделей."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimeStampedModel(SQLModel, table=False):
    """Добавляет created_at / updated_at."""

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    def touch(self) -> None:
        self.updated_at = utcnow()


__all__ = ["TimeStampedModel", "utcnow"]

