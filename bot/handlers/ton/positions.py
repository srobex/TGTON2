"""Отображение активных позиций и правил авто-продажи."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import get_or_create_user, list_rules_for_wallet
from bot.utils.i18n import get_i18n

router = Router(name="ton-positions")
i18n = get_i18n()


@router.message(Command("positions"))
async def command_positions(message: Message, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    user = await get_or_create_user(session, message.from_user)
    if not user.wallet_address:
        await message.answer(i18n.gettext("positions_connect_first", locale=locale))
        return
    rules = await list_rules_for_wallet(session, user.wallet_address)
    if not rules:
        await message.answer(i18n.gettext("positions_empty", locale=locale))
        return
    lines = [i18n.gettext("positions_header", locale=locale)]
    for idx, rule in enumerate(rules, start=1):
        current_value = (rule.amount_jetton or 0) * (rule.avg_price_usd or 0)
        lines.append(
            i18n.gettext(
                "positions_row",
                locale=locale,
                idx=idx,
                jetton=rule.jetton_address,
                tp=rule.take_profit_usd,
                stop=rule.stop_loss_usd or "-",
                amount=f"{rule.amount_jetton or 0:.2f}",
                avg=f"{rule.avg_price_usd or 0:.4f}",
                value=f"{current_value:.2f}",
                created=rule.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        )
    await message.answer("\n".join(lines))


__all__ = ["router", "command_positions"]

