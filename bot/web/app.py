"""FastAPI backend для Mini App Ton Connect и интеграции с HyperSniper Indexer."""

from __future__ import annotations

import hmac
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bot.context import gem_scanner, ton_connect
from bot.middlewares.db import get_session_maker
from bot.repositories import ensure_user_by_telegram_id
from bot.services.ton.ton_direct import JettonMinterEvent
from bot.utils.security import decode_session_token
from bot.web.webhooks import WebhookSubscription, get_webhook_subscribers, register_webhook
from config.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=True)
session_maker = get_session_maker()
settings = get_settings()


# ============================================================================
# Модели для Webhook от HyperSniper Indexer
# ============================================================================

class IndexerJettonInfo(BaseModel):
    """Информация о Jetton из индексера."""
    name: str = ""
    symbol: str = ""
    decimals: int = 9
    total_supply: str = ""
    content_uri: str | None = None


class IndexerAdminInfo(BaseModel):
    """Информация об админе Jetton."""
    address: str = ""
    is_contract: bool = False


class IndexerFlagsInfo(BaseModel):
    """Флаги верификации."""
    mintable: bool = False
    verified_by_interface: bool = False
    known_code_hash: bool = False


class IndexerMetaInfo(BaseModel):
    """Метаданные события."""
    block_unixtime: int = 0
    indexer_unixtime: int = 0
    latency_ms: int = 0
    minter_type: str = ""


class IndexerLinksInfo(BaseModel):
    """Ссылки на обозреватели."""
    tonviewer: str = ""
    tonscan: str = ""
    dexscreener: str = ""


class IndexerWebhookPayload(BaseModel):
    """Полный payload от HyperSniper Indexer."""
    event: str
    minter_address: str
    workchain: int = 0
    seqno: int = 0
    tx_hash: str = ""
    tx_lt: int = 0
    code_hash: str = ""
    jetton: IndexerJettonInfo = Field(default_factory=IndexerJettonInfo)
    admin: IndexerAdminInfo = Field(default_factory=IndexerAdminInfo)
    flags: IndexerFlagsInfo = Field(default_factory=IndexerFlagsInfo)
    meta: IndexerMetaInfo = Field(default_factory=IndexerMetaInfo)
    links: IndexerLinksInfo = Field(default_factory=IndexerLinksInfo)


class TokenPayload(BaseModel):
    sub: int = Field(..., description="Telegram user id")


class TonConnectLinkResponse(BaseModel):
    url: str


class TonConnectApproveRequest(BaseModel):
    wallet_address: str
    public_key: str
    device: str | None = None


class TonConnectApproveResponse(BaseModel):
    status: str = "ok"


class GemTopResponse(BaseModel):
    tokens: list[dict]


class WebhookRequest(BaseModel):
    callback_url: str
    min_score: float = 60.0


async def get_db_session():
    async with session_maker() as session:
        yield session


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> int:
    try:
        payload = decode_session_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return int(payload["sub"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Возможное место для фоновых задач (тоннель, тепловые карты, etc.)
    yield


app = FastAPI(title="HyperSniper Mini App API", lifespan=lifespan)


@app.post("/api/ton-connect/link", response_model=TonConnectLinkResponse)
async def create_ton_connect_link(user_id: int = Depends(get_user_id)) -> TonConnectLinkResponse:
    url = ton_connect.create_connection_url(user_id)
    return TonConnectLinkResponse(url=url)


@app.post("/api/ton-connect/approve", response_model=TonConnectApproveResponse)
async def approve_ton_connect(
    payload: TonConnectApproveRequest,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> TonConnectApproveResponse:
    user = await ensure_user_by_telegram_id(session, user_id)
    await ton_connect.attach_wallet(
        session,
        wallet_address=payload.wallet_address,
        public_key=payload.public_key,
        device=payload.device or "mini-app",
        user=user,
    )
    return TonConnectApproveResponse()


@app.get("/api/gem/top", response_model=GemTopResponse)
async def api_gem_top(limit: int = 10) -> GemTopResponse:
    tokens = await gem_scanner.get_top(limit=limit)
    return GemTopResponse(tokens=[token.as_dict() for token in tokens])


@app.post("/api/webhooks", status_code=201)
async def register_webhook_endpoint(req: WebhookRequest, user_id: int = Depends(get_user_id)) -> dict:
    register_webhook(user_id, WebhookSubscription(callback_url=req.callback_url, min_score=req.min_score))
    return {"status": "ok"}


# ============================================================================
# Endpoint для приёма событий от HyperSniper Indexer
# ============================================================================

@app.post("/api/indexer/event")
async def receive_indexer_event(
    payload: IndexerWebhookPayload,
    x_hypersniper_event: str | None = Header(None, alias="X-HyperSniper-Event"),
) -> dict:
    """Принимает события от HyperSniper Indexer.
    
    Индексер отправляет POST запрос при обнаружении нового JettonMinter.
    Бот преобразует данные и передаёт в GemScanner для обработки.
    """
    # Проверяем тип события
    if payload.event != "jetton_minter_deployed":
        logger.debug("Получено неизвестное событие от индексера: {event}", event=payload.event)
        return {"status": "ignored", "reason": "unknown_event"}
    
    logger.info(
        "📥 Получено событие от индексера: {symbol} ({address})",
        symbol=payload.jetton.symbol or "???",
        address=payload.minter_address[:16] + "...",
    )
    
    # Преобразуем в формат JettonMinterEvent для GemScanner
    event = JettonMinterEvent(
        address=payload.minter_address,
        owner_address=payload.admin.address if payload.admin.address else None,
        total_supply=int(payload.jetton.total_supply) if payload.jetton.total_supply.isdigit() else None,
        symbol=payload.jetton.symbol if payload.jetton.symbol else None,
        timestamp=payload.meta.block_unixtime or int(datetime.now(timezone.utc).timestamp()),
        raw={
            "source": "hypersniper_indexer",
            "code_hash": payload.code_hash,
            "tx_hash": payload.tx_hash,
            "workchain": payload.workchain,
            "seqno": payload.seqno,
            "latency_ms": payload.meta.latency_ms,
            "minter_type": payload.meta.minter_type,
            "flags": {
                "mintable": payload.flags.mintable,
                "verified_by_interface": payload.flags.verified_by_interface,
                "known_code_hash": payload.flags.known_code_hash,
            },
            "links": {
                "tonviewer": payload.links.tonviewer,
                "tonscan": payload.links.tonscan,
                "dexscreener": payload.links.dexscreener,
            },
            "jetton_name": payload.jetton.name,
            "decimals": payload.jetton.decimals,
            "content_uri": payload.jetton.content_uri,
        },
    )
    
    # Передаём в GemScanner для обработки
    try:
        await gem_scanner._on_new_jetton(event)
        logger.info(
            "✅ Событие обработано GemScanner: {symbol}",
            symbol=payload.jetton.symbol or payload.minter_address[:12],
        )
        return {"status": "processed", "address": payload.minter_address}
    except Exception as exc:
        logger.error("❌ Ошибка обработки события: {error}", error=str(exc))
        return {"status": "error", "reason": str(exc)}


@app.get("/api/indexer/health")
async def indexer_health() -> dict:
    """Проверка доступности endpoint для индексера."""
    return {
        "status": "ok",
        "service": "hypersniper-bot",
        "ready_for_indexer": True,
    }

