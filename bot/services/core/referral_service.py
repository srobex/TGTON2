"""Реферальная система HyperSniper (Omniston payload 0.8–1%)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from bot.models import ReferralLink, User
from config.settings import get_settings


@dataclass(slots=True)
class ReferralStats:
    """Агрегированные данные по рефералу."""

    invited: int = 0
    volume_usd: float = 0.0
    rewards_usd: float = 0.0
    last_payout: datetime | None = None


class ReferralService:
    """Реферальная система, работающая через БД."""

    def __init__(self) -> None:
        cfg = get_settings().referral
        self._fee_percent = cfg.default_fee_percent
        self._payload = cfg.omniston_payload
        self._reward_delay = cfg.reward_delay_sec

    @property
    def payload(self) -> str:
        return self._payload

    async def link(
        self,
        session: AsyncSession,
        *,
        referrer_code: str,
        invitee: User,
    ) -> User | None:
        """Привязывает пользователя к рефереру по его коду."""

        if not referrer_code:
            return None
        stmt_referrer = select(User).where(User.referral_code == referrer_code)
        referrer = (await session.exec(stmt_referrer)).one_or_none()
        if referrer is None or referrer.id == invitee.id:
            return None

        stmt_existing = select(ReferralLink).where(ReferralLink.invitee_id == invitee.id)
        if (await session.exec(stmt_existing)).one_or_none():
            return None

        link = ReferralLink(referrer_id=referrer.id, invitee_id=invitee.id)
        session.add(link)
        await session.commit()
        logger.info("Новая рефералка: {ref} -> {inv}", ref=referrer.id, inv=invitee.id)
        return referrer

    async def record_trade(
        self,
        session: AsyncSession,
        *,
        invitee: User,
        volume_usd: float,
    ) -> float:
        """Начисляет награду рефереру за оборот приглашённого пользователя."""

        stmt = select(ReferralLink).where(ReferralLink.invitee_id == invitee.id)
        referral = (await session.exec(stmt)).one_or_none()
        if referral is None:
            return 0.0
        referral.volume_usd += volume_usd
        reward = volume_usd * self._fee_percent / 100
        referral.reward_usd += reward
        referral.last_payout = datetime.now(timezone.utc)
        session.add(referral)
        await session.commit()
        return reward

    async def get_stats(self, session: AsyncSession, user: User) -> ReferralStats:
        stmt = select(
            func.count(ReferralLink.id),
            func.coalesce(func.sum(ReferralLink.volume_usd), 0.0),
            func.coalesce(func.sum(ReferralLink.reward_usd), 0.0),
        ).where(ReferralLink.referrer_id == user.id)
        invited, volume, rewards = (await session.exec(stmt)).one()
        return ReferralStats(
            invited=int(invited or 0),
            volume_usd=float(volume or 0.0),
            rewards_usd=float(rewards or 0.0),
        )

    def build_link(self, bot_username: str, user: User) -> str:
        username = bot_username.lstrip("@")
        return f"https://t.me/{username}?start=ref_{user.referral_code}"


__all__ = ["ReferralService", "ReferralStats"]

