"""Реферальная программа /referral."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.context import referral_service, settings
from bot.repositories import get_or_create_user
from bot.utils.i18n import get_i18n

router = Router(name="core-referral")
i18n = get_i18n()


@router.message(Command("referral"))
async def command_referral(message: Message, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    user = await get_or_create_user(session, message.from_user)
    stats = await referral_service.get_stats(session, user)
    bot_username = message.bot.username or settings.telegram.app_name
    link = referral_service.build_link(bot_username, user)
    text = i18n.gettext(
        "referral_overview",
        locale=locale,
        invited=stats.invited,
        volume=f"{stats.volume_usd:,.2f}",
        rewards=f"{stats.rewards_usd:,.2f}",
    )
    text += "\n" + i18n.gettext("referral_link", locale=locale, link=link)
    await message.answer(text)


__all__ = ["router"]

