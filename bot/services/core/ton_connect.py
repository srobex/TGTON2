"""Ton Connect 2.0 backend для HyperSniper.

Pytonconnect даёт чистую интеграцию без API-ключей: мы формируем запросы,
подписываем их на стороне пользователя и валидируем результат.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram.types import User as TelegramUser
from loguru import logger
from pytonconnect import TonConnect
from pytonconnect.exceptions import TonConnectError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from bot.models import User
from bot.repositories import (
    attach_wallet_data,
    clear_wallet_data,
    ensure_user_by_telegram_id,
    get_or_create_user,
    get_user_by_telegram,
    get_user_by_wallet,
)
from config.settings import get_settings


@dataclass(slots=True)
class WalletSession:
    """Информация о подключённом кошельке."""

    user_id: int
    wallet_address: str
    public_key: str
    device: str
    last_active: datetime
    session_token: str

    def is_expired(self, lifetime_minutes: int) -> bool:
        return datetime.now(timezone.utc) - self.last_active > timedelta(minutes=lifetime_minutes)


class TonConnectService:
    """Управляет Ton Connect ссылками и сессиями Mini App."""

    def __init__(self) -> None:
        settings = get_settings()
        self._manifest_url = settings.telegram.mini_app_url
        self._session_lifetime = 60  # минут
        self._connector = TonConnect(manifest_url=str(self._manifest_url) if self._manifest_url else "")
        self._sessions: dict[int, WalletSession] = {}
        self._wallet_index: dict[str, int] = {}
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    def create_connection_url(self, user_id: int) -> str:
        """Формирует URL для Ton Connect Mini App."""

        session_token = secrets.token_urlsafe(16)
        payload = {"user_id": user_id, "session": session_token}
        url = self._connector.create_link(json.dumps(payload))
        logger.debug("TonConnect URL для пользователя {user}: {url}", user=user_id, url=url)
        return url

    def set_session_maker(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    async def preload_wallets(self) -> None:
        """Загружает индексы кошельков из БД (используется при старте)."""

        if self._session_maker is None:
            return
        async with self._session_maker() as session:
            stmt = select(User).where(User.wallet_address.is_not(None))
            result = await session.exec(stmt)
            users = result.all()
            for user in users:
                if user.wallet_address:
                    self._wallet_index[user.wallet_address] = user.telegram_id

    async def attach_wallet(
        self,
        session: AsyncSession,
        *,
        wallet_address: str,
        public_key: str,
        device: str,
        tg_user: TelegramUser | None = None,
        user: User | None = None,
        telegram_id: int | None = None,
    ) -> WalletSession:
        """Сохраняет кошелёк и в памяти, и в базе."""

        if user is None:
            if tg_user is not None:
                user = await get_or_create_user(session, tg_user)
            elif telegram_id is not None:
                user = await ensure_user_by_telegram_id(session, telegram_id)
            else:
                raise ValueError("Не указан источник данных для пользователя Ton Connect")
        await attach_wallet_data(
            session,
            user,
            wallet_address=wallet_address,
            public_key=public_key,
            device=device,
        )
        wallet_session = WalletSession(
            user_id=user.telegram_id,
            wallet_address=wallet_address,
            public_key=public_key,
            device=device,
            last_active=datetime.now(timezone.utc),
            session_token=secrets.token_hex(16),
        )
        self._sessions[user.telegram_id] = wallet_session
        self._wallet_index[wallet_address] = user.telegram_id
        logger.info("Пользователь {user} подключил кошелёк {wallet}", user=user.telegram_id, wallet=wallet_address)
        return wallet_session

    def get_session(self, user_id: int) -> WalletSession | None:
        session = self._sessions.get(user_id)
        if not session:
            return None
        if session.is_expired(self._session_lifetime):
            logger.debug("TonConnect сессия пользователя {user} истекла", user=user_id)
            expired = self._sessions.pop(user_id, None)
            if expired:
                self._wallet_index.pop(expired.wallet_address, None)
            return None
        session.last_active = datetime.now(timezone.utc)
        return session

    async def detach_wallet(self, user_id: int, session: AsyncSession | None = None) -> None:
        """Разрывает Ton Connect сессию и очищает БД."""

        wallet_session = self._sessions.pop(user_id, None)
        if wallet_session:
            self._wallet_index.pop(wallet_session.wallet_address, None)
        if session:
            await self._clear_wallet_db(session, user_id, wallet_session)
        elif self._session_maker:
            async with self._session_maker() as db_session:
                await self._clear_wallet_db(db_session, user_id, wallet_session)
        logger.info("TonConnect сессия пользователя {user} удалена", user=user_id)

    async def find_user_by_wallet(self, wallet_address: str) -> int | None:
        """Возвращает user_id по адресу кошелька."""

        cached = self._wallet_index.get(wallet_address)
        if cached:
            return cached
        if self._session_maker is None:
            return None
        async with self._session_maker() as session:
            user = await get_user_by_wallet(session, wallet_address)
            if user:
                self._wallet_index[wallet_address] = user.telegram_id
                return user.telegram_id
        return None

    async def _clear_wallet_db(
        self,
        session: AsyncSession,
        user_id: int,
        wallet_session: WalletSession | None,
    ) -> None:
        if wallet_session and wallet_session.wallet_address:
            db_user = await get_user_by_wallet(session, wallet_session.wallet_address)
        else:
            db_user = await get_user_by_telegram(session, user_id)
        if db_user:
            await clear_wallet_data(session, db_user)

    def sign_payload(self, user_id: int, payload: str) -> str:
        """Инициирует подпись сообщения пользователем."""

        session = self.get_session(user_id)
        if session is None:
            raise TonConnectError("Кошелёк не подключён")
        try:
            result = self._connector.request_sign(payload, session.public_key)
        except TonConnectError as exc:
            logger.error("TonConnect подпись не удалась: {error}", error=exc)
            raise
        return result


__all__ = ["TonConnectService", "WalletSession"]

