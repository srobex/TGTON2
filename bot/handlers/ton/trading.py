"""Quick Buy/Sell и управление тейк-профитами."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.context import swap_service, ton_connect
from bot.repositories import get_or_create_user
from bot.utils.i18n import get_i18n

router = Router(name="ton-trading")
i18n = get_i18n()


@router.message(Command("buy"))
async def handle_buy(message: Message, command: CommandObject) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer(i18n.gettext("buy_usage", locale=locale))
        return
    token_address, amount_raw = args[0], args[1]
    try:
        amount_ton = float(amount_raw)
    except ValueError:
        await message.answer(i18n.gettext("buy_amount_invalid", locale=locale))
        return
    session = ton_connect.get_session(message.from_user.id)
    if session is None:
        link = ton_connect.create_connection_url(message.from_user.id)
        await message.answer(i18n.gettext("gem_connect_instructions", locale=locale, link=link))
        return
    quote = await swap_service.prepare_buy(
        wallet=session.wallet_address,
        jetton=token_address,
        amount_ton=amount_ton,
        slippage_percent=5.0,
    )
    await message.answer(
        i18n.gettext(
            "buy_quote",
            locale=locale,
            token=token_address,
            amount=amount_ton,
            est=f"{quote.estimated_receive:.4f}",
            min_receive=f"{quote.min_receive:.4f}",
            fee=quote.fee_nano,
        )
    )


@router.message(Command("sell"))
async def handle_sell(message: Message, command: CommandObject) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer(i18n.gettext("sell_usage", locale=locale))
        return
    token_address, amount_raw = args[0], args[1]
    try:
        amount_jetton = float(amount_raw)
    except ValueError:
        await message.answer(i18n.gettext("sell_amount_invalid", locale=locale))
        return
    session = ton_connect.get_session(message.from_user.id)
    if session is None:
        link = ton_connect.create_connection_url(message.from_user.id)
        await message.answer(i18n.gettext("gem_connect_instructions", locale=locale, link=link))
        return
    quote = await swap_service.prepare_sell(
        wallet=session.wallet_address,
        jetton=token_address,
        amount_jetton=amount_jetton,
        slippage_percent=6.0,
    )


@router.message(Command("autotp"))
async def handle_auto_tp(message: Message, command: CommandObject, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer(i18n.gettext("autotp_usage", locale=locale))
        return
    token_address = args[0]
    try:
        tp_price = float(args[1])
        stop_price = float(args[2]) if len(args) >= 3 else None
    except ValueError:
        await message.answer(i18n.gettext("autotp_invalid", locale=locale))
        return
    ton_session = ton_connect.get_session(message.from_user.id)
    if ton_session is None:
        link = ton_connect.create_connection_url(message.from_user.id)
        await message.answer(i18n.gettext("gem_connect_instructions", locale=locale, link=link))
        return
    user = await get_or_create_user(session, message.from_user)
    position_id = f"{message.from_user.id}:{token_address}:{int(tp_price*1000)}"
    await swap_service.register_take_profit(
        session,
        position_id=position_id,
        user_id=user.id,
        wallet=ton_session.wallet_address,
        jetton=token_address,
        trigger_price_usd=tp_price,
        stop_price_usd=stop_price,
    )
    text = i18n.gettext(
        "autotp_set",
        locale=locale,
        token=token_address,
        tp=tp_price,
        stop=stop_price or "-",
        pid=position_id,
    )
    await message.answer(text)


@router.message(Command("autooff"))
async def handle_auto_off(message: Message, command: CommandObject, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    position_id = (command.args or "").strip()
    if not position_id:
        await message.answer(i18n.gettext("autooff_usage", locale=locale))
        return
    ton_session = ton_connect.get_session(message.from_user.id)
    if ton_session is None:
        await message.answer(i18n.gettext("positions_connect_first", locale=locale))
        return
    await swap_service.remove_rule(session, position_id)
    await message.answer(i18n.gettext("autooff_done", locale=locale, pid=position_id))
    await message.answer(
        i18n.gettext(
            "sell_quote",
            locale=locale,
            token=token_address,
            amount=amount_jetton,
            est=f"{quote.estimated_receive:.4f}",
            min_receive=f"{quote.min_receive:.4f}",
            fee=quote.fee_nano,
        )
    )


__all__ = ["router"]

