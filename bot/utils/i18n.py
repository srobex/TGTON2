"""Лёгкая и сверхбыстрая система мультиязычности HyperSniper.

Особенности:
- JSON-словарь на каждый язык (locales/<lang>.json).
- Fallback к дефолтному языку при отсутствии ключа.
- Поддержка плейсхолдеров через str.format.
- Возможность горячей перезагрузки без рестарта бота.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import get_settings


class I18nManager:
    """Отвечает за загрузку и выдачу переводов."""

    def __init__(self) -> None:
        settings = get_settings()
        self._default_locale = settings.localization.default_locale
        self._enabled_locales = set(settings.localization.enabled_locales)
        self._locales_path = settings.localization.locales_path
        self._locales_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, str]] = {}
        self.reload()

    @property
    def default_locale(self) -> str:
        return self._default_locale

    @property
    def enabled_locales(self) -> tuple[str, ...]:
        return tuple(sorted(self._enabled_locales))

    def reload(self) -> None:
        """Полностью перезагружает локали (например, после деплоя)."""

        self._cache.clear()
        for locale in self._enabled_locales:
            locale_file = self._locales_path / f"{locale}.json"
            if not locale_file.exists():
                logger.warning(
                    "Локаль {locale} пропущена: отсутствует файл {path}",
                    locale=locale,
                    path=locale_file,
                )
                continue
            try:
                self._cache[locale] = json.loads(locale_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.error(
                    "Не удалось прочитать локаль {locale}: {error}",
                    locale=locale,
                    error=exc,
                )
                continue
        logger.info(
            "Загружены локали: {locales}",
            locales=", ".join(self._cache.keys()) or "нет",
        )

    def detect_locale(self, hint: str | None) -> str:
        """Определяет язык пользователя (UA/RU/EN -> ru/en)."""

        if hint:
            normalized = hint.lower().split("-")[0]
            if normalized in self._enabled_locales:
                return normalized
        return self._default_locale

    def gettext(self, key: str, locale: str | None = None, **kwargs: Any) -> str:
        """Возвращает перевод по ключу с учётом языка и fallback."""

        target_locale = locale if locale in self._enabled_locales else self._default_locale
        value = self._cache.get(target_locale, {}).get(key)
        if value is None and target_locale != self._default_locale:
            value = self._cache.get(self._default_locale, {}).get(key)
        if value is None:
            logger.debug("Ключ локали не найден: {key}", key=key)
            value = key
        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError as exc:
                logger.error("Отсутствует плейсхолдер {placeholder} для ключа {key}", placeholder=exc, key=key)
        return value


@lru_cache(maxsize=1)
def get_i18n() -> I18nManager:
    """Ленивая инициализация менеджера переводов."""

    return I18nManager()


__all__ = ["get_i18n", "I18nManager"]




