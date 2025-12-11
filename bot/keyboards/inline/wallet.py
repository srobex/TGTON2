"""Клавиатуры для Ton Connect."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_wallet_keyboard(connected: bool) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="wallet:refresh")],
    ]
    if connected:
        buttons.append(
            [InlineKeyboardButton(text="❌ Отключить", callback_data="wallet:disconnect")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = ["build_wallet_keyboard"]




