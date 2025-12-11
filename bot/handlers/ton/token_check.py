"""Проверка jetton по команде пользователя."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message

from bot.context import safety_checker
from bot.utils.i18n import get_i18n

router = Router(name="ton-token-check")
i18n = get_i18n()


@router.message(Command("check"))
async def handle_check(message: Message, command: CommandObject) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    token_address = (command.args or "").strip()
    if not token_address:
        await message.answer(i18n.gettext("check_usage", locale=locale))
        return
    report = await safety_checker.check_jetton(token_address)
    text = i18n.gettext(
        "check_report",
        locale=locale,
        token=token_address,
        safe="Да" if report.is_safe else "Нет",
        score=f"{report.score:.1f}",
        liquidity=f"{report.liquidity_usd:,.0f}",
        volume=f"{report.volume_5m_usd:,.0f}",
        reasons=", ".join(report.reasons) or "-",
    )
    await message.answer(text)


__all__ = ["router"]

