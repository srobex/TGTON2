"""Базовые хендлеры HyperSniper (старт, меню, язык, быстрые команды)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.context import bot, gem_scanner, referral_service, settings
from bot.keyboards.reply import build_main_menu_keyboard
from bot.models import User
from bot.repositories import get_or_create_user
from bot.utils.i18n import get_i18n

router = Router(name="core-common")
i18n = get_i18n()


@router.message(CommandStart(ignore_case=True))
async def handle_start(
    message: Message,
    command: CommandObject | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Приветствие + автодетект языка."""

    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    user = None
    if session is not None:
        user = await get_or_create_user(session, message.from_user)
    if command and command.args and session is not None and user is not None:
        await _process_start_payload(command.args, session, user)
    greeting = i18n.gettext("welcome_message", locale=locale, username=message.from_user.full_name)
    await message.answer(greeting, reply_markup=_build_lang_keyboard(locale))


@router.message(Command("menu"))
async def handle_menu(message: Message) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    text = i18n.gettext(
        "menu_hint",
        locale=locale,
        bot=settings.telegram.app_name,
    )
    await message.answer(text, reply_markup=build_main_menu_keyboard())


@router.message(Command("hot"))
async def handle_hot_tokens(message: Message) -> None:
    """Показывает топ Gem Hunter прямо в чате."""

    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    tokens = await gem_scanner.get_top()
    if not tokens:
        await message.answer(i18n.gettext("hot_empty", locale=locale))
        return
    lines = []
    for idx, token in enumerate(tokens, start=1):
        tags = ", ".join(token.tags) if token.tags else i18n.gettext("tag_unknown", locale=locale)
        lines.append(
            i18n.gettext(
                "hot_line",
                locale=locale,
                idx=idx,
                symbol=token.symbol or token.address[-6:],
                score=f"{token.score:.1f}",
                tags=tags,
            )
        )
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("lang:"))
async def handle_language_switch(callback: CallbackQuery) -> None:
    """Переключение языка одним нажатием."""

    if not callback.data:
        return
    locale = callback.data.split(":", maxsplit=1)[1]
    if locale not in i18n.enabled_locales:
        await callback.answer("Язык скоро появится", show_alert=True)
        return
    text = i18n.gettext("language_switched", locale=locale, language=locale.upper())
    try:
        await callback.message.edit_text(text, reply_markup=_build_lang_keyboard(locale))
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
    await callback.message.answer(
        i18n.gettext("menu_hint", locale=locale, bot=settings.telegram.app_name),
        reply_markup=build_main_menu_keyboard(),
    )
    await callback.answer()


def _build_lang_keyboard(active_locale: str) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Русский 🇷🇺" + (" ✅" if active_locale == "ru" else ""),
                callback_data="lang:ru",
            ),
            InlineKeyboardButton(
                text="English 🇬🇧" + (" ✅" if active_locale == "en" else ""),
                callback_data="lang:en",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _process_start_payload(payload: str, session: AsyncSession, invitee: User) -> None:
    if not payload.startswith("ref_"):
        return
    try:
        ref_code = payload.split("_", maxsplit=1)[1]
    except (IndexError, ValueError):
        return
    referrer = await referral_service.link(session, referrer_code=ref_code, invitee=invitee)
    if referrer:
        text = i18n.gettext(
            "referral_new_invitee",
            locale=referrer.language or i18n.default_locale,
            username=invitee.username or str(invitee.telegram_id),
        )
        try:
            await bot.send_message(chat_id=referrer.telegram_id, text=text)
        except Exception:  # noqa: BLE001
            pass


__all__ = ["router"]

