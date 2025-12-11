# Stage 7 — Production Checklist

## Логирование / метрики
- Использовать `loguru` JSON sink (пример в `bot/logging_config.py`).
- Метрики через Prometheus (`/metrics` endpoint FastAPI) + экспортер для aiogram.

## Тестирование / CI
- Unit tests: `pytest` для сервисов (GemScanner, SwapService, TonConnectService).
- Интеграционные тесты: запуск mock toncenter и тонкого price feed.
- CI: GitHub Actions (lint + tests), деплой в Docker Registry.

## Деплой
- Dockerfile + docker-compose (redis, sqlite/postgres, bot, fastapi).
- Kubernetes: отдельные deployment для bot, fastapi, price feed.




