"""Функции для работы с таблицей пользователей."""

from __future__ import annotations

from typing import Optional

from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from bot.models import User


async def get_or_create_user(
    session: AsyncSession,
    tg_user: TelegramUser,
) -> User:
    stmt = select(User).where(User.telegram_id == tg_user.id)
    result = await session.exec(stmt)
    user = result.one_or_none()
    if user:
        user.username = tg_user.username
        user.language = tg_user.language_code or user.language
        user.touch()
    else:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            language=tg_user.language_code or "auto",
        )
        session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def attach_wallet_data(
    session: AsyncSession,
    user: User,
    *,
    wallet_address: str,
    public_key: str,
    device: str | None = None,
) -> User:
    user.wallet_address = wallet_address
    user.public_key = public_key
    if device:
        user.device = device
    user.touch()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_ref_code(session: AsyncSession, code: str) -> Optional[User]:
    stmt = select(User).where(User.referral_code == code)
    result = await session.exec(stmt)
    return result.one_or_none()


async def get_user_by_wallet(session: AsyncSession, wallet: str) -> Optional[User]:
    stmt = select(User).where(User.wallet_address == wallet)
    result = await session.exec(stmt)
    return result.one_or_none()


async def get_user_by_telegram(session: AsyncSession, telegram_id: int) -> Optional[User]:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.exec(stmt)
    return result.one_or_none()


async def ensure_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User:
    user = await get_user_by_telegram(session, telegram_id)
    if user:
        return user
    user = User(telegram_id=telegram_id, language="auto")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def clear_wallet_data(session: AsyncSession, user: User) -> User:
    user.wallet_address = None
    user.public_key = None
    user.device = None
    user.touch()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


__all__ = [
    "attach_wallet_data",
    "ensure_user_by_telegram_id",
    "clear_wallet_data",
    "get_or_create_user",
    "get_user_by_ref_code",
    "get_user_by_telegram",
    "get_user_by_wallet",
]

