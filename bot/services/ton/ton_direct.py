"""Прямой доступ к сети TON без API-ключей.

TonDirectClient выполняет две ключевые задачи:
1. Высокоскоростные HTTP RPC вызовы (tonsdk совместимо с toncenter).
2. Постоянное WebSocket-подключение к публичному toncenter для ловли свежих JettonMinter.

Модуль спроектирован модульно и может быть переиспользован для других цепей через плагины.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import aiohttp
from loguru import logger

from config.settings import get_settings


class TonDirectError(RuntimeError):
    """Базовое исключение слоя прямого подключения к TON."""


@dataclass(slots=True)
class JettonMinterEvent:
    """Событие появления нового JettonMinter."""

    address: str
    owner_address: str | None
    total_supply: int | None
    symbol: str | None
    timestamp: int
    raw: dict[str, Any]


class TonDirectClient:
    """Лёгкий tonsdk-клиент поверх публичных toncenter RPC/WebSocket."""

    def __init__(self) -> None:
        settings = get_settings()
        self._rpc_endpoint = str(settings.ton.rpc_endpoint)
        self._ws_endpoint = str(settings.ton.ws_endpoint)
        self._ws_headers: dict[str, str] | None = None
        self._ws_endpoint = self._normalize_ws_endpoint(self._ws_endpoint)
        self._network = settings.ton.network
        self._use_websocket = settings.ton.use_websocket
        self._session: aiohttp.ClientSession | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._callbacks: set[Callable[[JettonMinterEvent], Awaitable[None]]] = set()
        self._ws_reconnect_delay = 3
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Инициализирует HTTP session и (опционально) запускает WebSocket поток."""

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        
        if self._use_websocket:
            if self._ws_task is None or self._ws_task.done():
                self._stop_event.clear()
                self._ws_task = asyncio.create_task(self._run_ws_loop(), name="ton-ws-loop")
            logger.info(
                "TonDirectClient готов: RPC {rpc}, WS {ws}",
                rpc=self._rpc_endpoint,
                ws=self._ws_endpoint,
            )
        else:
            logger.info(
                "TonDirectClient готов: RPC {rpc}, WebSocket ОТКЛЮЧЁН (используем индексер)",
                rpc=self._rpc_endpoint,
            )

    async def close(self) -> None:
        """Чисто останавливает соединения."""

        self._stop_event.set()
        if self._ws_task:
            self._ws_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()

    async def rpc_call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Выполняет JSON-RPC вызов к toncenter."""

        if self._session is None:
            raise TonDirectError("HTTP-сессия не инициализирована, вызовите start()")
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        async with self._session.post(self._rpc_endpoint, json=payload) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise TonDirectError(f"RPC {method} завершился с HTTP {resp.status}: {text}")
            data = await resp.json()
            if "error" in data:
                raise TonDirectError(f"RPC ошибка {method}: {data['error']}")
            return data.get("result")

    async def get_jetton_data(self, address: str) -> dict[str, Any]:
        """Возвращает данные JettonMinter через tonsdk get-method."""

        return await self.rpc_call(
            "getJettonData",
            {"address": address, "network": self._network},
        )

    async def simulate_tx(self, body_boc: str, address: str) -> dict[str, Any]:
        """simulateMessageProcess для honeypot/safety checker."""

        return await self.rpc_call(
            "simulateMessageProcess",
            {"address": address, "boc": body_boc, "network": self._network},
        )

    async def estimate_fee(self, message_boc: str) -> dict[str, Any]:
        """Приблизительная комиссия для buy/sell операций."""

        return await self.rpc_call(
            "estimateFee",
            {"boc": message_boc, "network": self._network},
        )

    def subscribe_jetton_minters(
        self,
        callback: Callable[[JettonMinterEvent], Awaitable[None]],
    ) -> None:
        """Регистрирует обработчик для новых JettonMinter."""

        self._callbacks.add(callback)

    async def _run_ws_loop(self) -> None:
        """Основной поток чтения WebSocket сообщений."""

        assert self._session is not None
        while not self._stop_event.is_set():
            try:
                async with self._session.ws_connect(
                    self._ws_endpoint,
                    heartbeat=20,
                    headers=self._ws_headers,
                ) as ws:
                    await ws.send_json(
                        {
                            "type": "subscribe",
                            "topic": "jetton-minter-created",
                            "network": self._network,
                        }
                    )
                    logger.info("Подписка на JettonMinter активирована")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_payload(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            raise TonDirectError(f"WS ошибка: {ws.exception()}")
            except Exception as exc:  # noqa: BLE001
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "WS toncenter отвалился: {error}, переподключение через {delay}s",
                    error=str(exc),
                    delay=self._ws_reconnect_delay,
                )
                await asyncio.sleep(self._ws_reconnect_delay)

    async def _handle_ws_payload(self, raw: str) -> None:
        """Обработка входящих WS сообщений."""

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Не удалось декодировать WS сообщение: {raw}", raw=raw)
            return
        if data.get("type") != "jetton-minter-created":
            return
        event = JettonMinterEvent(
            address=data["payload"]["address"],
            owner_address=data["payload"].get("owner"),
            total_supply=int(data["payload"].get("total_supply") or 0) or None,
            symbol=data["payload"].get("symbol"),
            timestamp=int(data.get("timestamp", 0)),
            raw=data,
        )
        await self._dispatch_event(event)

    async def _dispatch_event(self, event: JettonMinterEvent) -> None:
        """Отправляет событие во все зарегистрированные колбэки."""

        if not self._callbacks:
            return
        await asyncio.gather(*(self._safe_call(cb, event) for cb in self._callbacks))

    async def _safe_call(
        self,
        callback: Callable[[JettonMinterEvent], Awaitable[None]],
        event: JettonMinterEvent,
    ) -> None:
        try:
            await callback(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Колбэк TonDirect упал: {error}", error=exc)

    def _normalize_ws_endpoint(self, endpoint: str) -> str:
        """Извлекает api_key из query и переносит его в заголовок."""

        parts = urlsplit(endpoint)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        api_key = query.pop("api_key", None)
        normalized = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )
        if api_key:
            self._ws_headers = {"X-API-Key": api_key}
        return normalized


_client: TonDirectClient | None = None


async def get_ton_client() -> TonDirectClient:
    """Возвращает синглтон TonDirectClient."""

    global _client
    if _client is None:
        _client = TonDirectClient()
        await _client.start()
    return _client


__all__ = ["TonDirectClient", "TonDirectError", "JettonMinterEvent", "get_ton_client"]




