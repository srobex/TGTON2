"""Команды Ton Connect: /connect, /wallet."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.wallet import build_wallet_keyboard
from bot.context import ton_connect
from bot.models import User
from bot.repositories import get_or_create_user
from bot.utils.i18n import get_i18n
from bot.utils.security import issue_session_token

router = Router(name="core-wallet")
i18n = get_i18n()


@router.message(Command("connect"))
async def command_connect(message: Message) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    link = await ton_connect.create_connection_url(message.from_user.id)
    await message.answer(i18n.gettext("connect_link", locale=locale, link=link))
    token = issue_session_token(message.from_user.id)
    await message.answer(i18n.gettext("connect_token", locale=locale, token=token))


@router.message(Command("wallet"))
async def command_wallet(message: Message, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    user = await get_or_create_user(session, message.from_user)
    text, keyboard = await _wallet_status(user, locale)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "wallet:refresh")
async def callback_wallet_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    user = await get_or_create_user(session, callback.from_user)
    text, keyboard = await _wallet_status(user, locale)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(i18n.gettext("wallet_refreshed", locale=locale))


@router.callback_query(F.data == "wallet:disconnect")
async def callback_wallet_disconnect(callback: CallbackQuery, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    user = await get_or_create_user(session, callback.from_user)
    await ton_connect.detach_wallet(user.telegram_id, session=session)
    text, keyboard = await _wallet_status(user, locale)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(i18n.gettext("wallet_disconnected", locale=locale), show_alert=True)


async def _wallet_status(user: User, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
    session = ton_connect.get_session(user.telegram_id)
    if not user.wallet_address:
        return (
            i18n.gettext("wallet_not_connected", locale=locale),
            build_wallet_keyboard(connected=False),
        )
    last_seen = (
        session.last_active.strftime("%Y-%m-%d %H:%M:%S")
        if session
        else user.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    )
    text = i18n.gettext(
        "wallet_status",
        locale=locale,
        address=user.wallet_address,
        device=session.device if session else (user.device or "unknown"),
        last=last_seen,
    )
    return text, build_wallet_keyboard(connected=True)


__all__ = ["router", "command_wallet", "command_connect"]

