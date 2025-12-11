"""Хранилище подписчиков на внешние вебхуки."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class WebhookSubscription:
    callback_url: str
    min_score: float = 60.0


_subscribers: Dict[str, WebhookSubscription] = {}


def register_webhook(user_id: int, subscription: WebhookSubscription) -> None:
    _subscribers[str(user_id)] = subscription


def get_webhook_subscribers() -> Dict[str, WebhookSubscription]:
    return dict(_subscribers)


__all__ = ["WebhookSubscription", "register_webhook", "get_webhook_subscribers"]




