"""Middleware для предоставления SQLModel сессии в хендлеры."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from config.settings import get_settings
from bot import models  # noqa: F401  импортируем модели для регистрации метаданных

settings = get_settings()
engine = create_async_engine(
    settings.database.dsn,
    echo=settings.database.echo,
    poolclass=NullPool,
)
session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Временная инициализация таблиц (до появления Alembic миграций)."""

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    return session_maker


class DatabaseMiddleware(BaseMiddleware):
    """Создаёт AsyncSession на время обработки апдейта."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with session_maker() as session:
            data["session"] = session
            return await handler(event, data)


__all__ = ["DatabaseMiddleware", "init_db", "get_session_maker"]

