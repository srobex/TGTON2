"""Inline-клавиатуры для Gem Hunter."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_gem_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="gem:refresh"),
                InlineKeyboardButton(text="📊 Фильтры", callback_data="gem:filters"),
            ]
        ]
    )


def build_token_keyboard(address: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Купить", callback_data=f"gem:buy:{address}"),
                InlineKeyboardButton(text="🛡 Safety", callback_data=f"gem:safety:{address}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Ещё токены", callback_data="gem:refresh"),
                InlineKeyboardButton(text="👀 Подписаться", callback_data=f"gem:watch:{address}"),
            ],
            [
                InlineKeyboardButton(text="📈 Тейк-профит", callback_data=f"gem:tp:{address}"),
                InlineKeyboardButton(text="💥 Анти-раг", callback_data=f"gem:ar:{address}"),
            ],
            [
                InlineKeyboardButton(text="🔥 В топ", callback_data=f"gem:pin:{address}"),
            ],
        ]
    )


__all__ = ["build_gem_list_keyboard", "build_token_keyboard"]

