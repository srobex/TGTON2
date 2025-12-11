"""Основная клавиатура с командами HyperSniper."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает reply-клавиатуру с основными командами."""

    buttons = [
        [
            KeyboardButton(text="/gem"),
            KeyboardButton(text="/hot"),
        ],
        [
            KeyboardButton(text="/connect"),
            KeyboardButton(text="/wallet"),
        ],
        [
            KeyboardButton(text="/positions"),
            KeyboardButton(text="/referral"),
        ],
        [
            KeyboardButton(text="/menu"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


__all__ = ["build_main_menu_keyboard"]




