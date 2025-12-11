"""Глобальные настройки HyperSniper.

Настройки разделены по доменам (Telegram, TON, кеш, реферальная система и т.д.),
что позволяет подключать новые цепочки и модули без переписывания базового кода.
Вся конфигурация загружается из переменных окружения через Pydantic Settings,
поэтому бот легко деплоить в любой инфраструктуре (Docker, Kubernetes, serverless).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    Field,
    PositiveFloat,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ACCESSIBLE_ENV_FILE = BASE_DIR / "config" / "runtime.env"
DEFAULT_ENV_FILE = BASE_DIR / ".env"
ENV_FILE = ACCESSIBLE_ENV_FILE if ACCESSIBLE_ENV_FILE.exists() else DEFAULT_ENV_FILE


class TelegramSettings(BaseModel):
    """Конфигурация Telegram-бота и Mini App."""

    token: str = Field(..., description="Токен бота @HyperSniper_bot")
    app_name: str = "HyperSniper"
    mini_app_url: AnyHttpUrl | None = Field(
        None, description="URL Mini App с Ton Connect 2.0"
    )
    webhook_domain: AnyHttpUrl | None = Field(
        None, description="Домен для вебхука (если работаем не через polling)"
    )
    admins: list[int] = Field(default_factory=list, description="ID операторов/админов")

    @field_validator("webhook_domain", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class TonCenterSettings(BaseModel):
    """Набор публичных RPC/WebSocket точек TON без API-ключей."""

    rpc_endpoint: AnyHttpUrl = Field(
        ..., description="HTTP RPC для tonsdk (без ключей, чистый публичный нод)"
    )
    ws_endpoint: AnyUrl = Field(
        ..., description="WebSocket toncenter для мгновенного Gem Hunter"
    )
    network: Literal["mainnet", "testnet"] = "mainnet"
    use_websocket: bool = Field(
        True, description="Использовать WebSocket toncenter (отключить если используем индексер)"
    )


class TonSecuritySettings(BaseModel):
    """Параметры безопасного трейдинга и симуляций."""

    simulate_workchain: int = 0
    max_safety_latency_ms: int = 600
    min_liquidity_usd: PositiveFloat = 5_000.0
    min_volume_5m_usd: PositiveFloat = 20_000.0
    honeypot_ban_score: PositiveFloat = 0.9
    blacklist_addresses: list[str] = Field(default_factory=list)
    trusted_smart_money: list[str] = Field(default_factory=list)


class CacheSettings(BaseModel):
    """Настройки кешей (aiocache поддерживает memory / redis)."""

    backend: Literal["memory", "redis"] = "memory"
    ttl_seconds: int = 30
    redis_dsn: str | None = None


class DatabaseSettings(BaseModel):
    """SQLModel + aiosqlite (по умолчанию) и готовность к Postgres."""

    dsn: str = Field(
        "sqlite+aiosqlite:///./database/hypersniper.db",
        description="Строка подключения SQLAlchemy/SQLModel",
    )
    echo: bool = False


class GemScannerSettings(BaseModel):
    """Параметры Alpha Scanner / Gem Hunter."""

    refresh_interval_sec: int = 15
    burst_threshold_tokens: int = 10
    min_liquidity_usd: PositiveFloat = 5_000.0
    min_volume_5m_usd: PositiveFloat = 20_000.0
    hot_growth_percent: PositiveFloat = 35.0


class PriceFeedSettings(BaseModel):
    """Конфигурация сервиса цен."""

    interval_sec: int = 10
    source_url: AnyHttpUrl = Field(
        "https://tonapi.io/v2/rates?tokens=",
        description="Эндпоинт tonapi/v2/rates или аналогичный",
    )
    request_timeout: int = 5


class ReferralSettings(BaseModel):
    """Реферальная система Omniston payload (non-custodial 0.8–1%)."""

    default_fee_percent: PositiveFloat = 0.9
    omniston_payload: str = Field(..., description="Payload для Omniston 0.8–1%")
    reward_delay_sec: int = 300


class LocalizationSettings(BaseModel):
    """Список доступных языков и язык по умолчанию."""

    default_locale: str = "ru"
    enabled_locales: list[str] = Field(default_factory=lambda: ["ru", "en"])
    locales_path: Path = BASE_DIR / "locales"


class SecuritySettings(BaseModel):
    """JWT и другие security-настройки для Mini App."""

    jwt_secret: SecretStr = Field(..., description="Секрет для подписания JWT")
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60


class AppSettings(BaseSettings):
    """Главный контейнер настроек HyperSniper."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Literal["dev", "prod"] = "dev"
    telegram: TelegramSettings
    ton: TonCenterSettings
    ton_security: TonSecuritySettings = TonSecuritySettings()
    cache: CacheSettings = CacheSettings()
    database: DatabaseSettings = DatabaseSettings()
    gem_scanner: GemScannerSettings = GemScannerSettings()
    price_feed: PriceFeedSettings = PriceFeedSettings()
    referral: ReferralSettings
    localization: LocalizationSettings = LocalizationSettings()
    security: SecuritySettings

    @property
    def is_production(self) -> bool:
        """True, если бот запущен в продовой среде."""

        return self.environment == "prod"


# Ленивый синглтон (избегаем глобальных переменных в модулях).
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Возвращает единый экземпляр настроек.

    Вызываем во всех частях приложения (handlers, services). Значения кэшируются,
    поэтому инициализация .env происходит ровно один раз за процесс.
    """

    global _settings
    if _settings is None:
        _settings = AppSettings()  # type: ignore[call-arg]
    return _settings


__all__ = [
    "AppSettings",
    "CacheSettings",
    "DatabaseSettings",
    "GemScannerSettings",
    "LocalizationSettings",
    "PriceFeedSettings",
    "ReferralSettings",
    "SecuritySettings",
    "TelegramSettings",
    "TonCenterSettings",
    "TonSecuritySettings",
    "get_settings",
]

