"""Основная клавиатура HyperSniper с локализованными кнопками."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.utils.i18n import get_i18n

i18n = get_i18n()


# Ключи кнопок для сопоставления с командами
BUTTON_KEYS = {
    "btn_gem": "/gem",
    "btn_hot": "/hot",
    "btn_wallet": "/wallet",
    "btn_connect": "/connect",
    "btn_positions": "/positions",
    "btn_referral": "/referral",
    "btn_settings": "/menu",
    "btn_help": "/help",
}


def build_main_menu_keyboard(locale: str = "ru") -> ReplyKeyboardMarkup:
    """Возвращает reply-клавиатуру с локализованными кнопками."""

    buttons = [
        [
            KeyboardButton(text=i18n.gettext("btn_gem", locale=locale)),
            KeyboardButton(text=i18n.gettext("btn_hot", locale=locale)),
        ],
        [
            KeyboardButton(text=i18n.gettext("btn_wallet", locale=locale)),
            KeyboardButton(text=i18n.gettext("btn_connect", locale=locale)),
        ],
        [
            KeyboardButton(text=i18n.gettext("btn_positions", locale=locale)),
            KeyboardButton(text=i18n.gettext("btn_referral", locale=locale)),
        ],
        [
            KeyboardButton(text=i18n.gettext("btn_settings", locale=locale)),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_command_by_button_text(text: str) -> str | None:
    """Возвращает команду по тексту кнопки (для любого языка)."""

    # Проверяем все локали
    for locale in i18n.enabled_locales:
        for key, command in BUTTON_KEYS.items():
            localized_text = i18n.gettext(key, locale=locale)
            if text == localized_text:
                return command
    return None


__all__ = ["build_main_menu_keyboard", "get_command_by_button_text", "BUTTON_KEYS"]
