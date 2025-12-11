# HyperSniper — король TON 2026

HyperSniper (@HyperSniper_bot) — это ультрабыстрый non-custodial бот для TON с Alpha Scanner / Gem Hunter, safety check < 600 мс и модульной архитектурой для подключения новых цепей за считанные минуты.

## Возможности MVP (Этап 1)
- ⚡ Прямое подключение к TON (tonsdk + toncenter WebSocket, без API-ключей).
- 🛡 Safety Checker: simulate_tx, honeypot, ликвидность/объём, smart money фильтры.
- 🧠 Alpha Scanner / Gem Hunter: ловит JettonMinter через WS, строит топ-10 горячих токенов, показывает метки `Smart money inside`, `LP burned`, `New`.
- 💸 Quick Buy/Sell, тейк-профиты и анти-раг через non-custodial инструкции.
- 🤝 Реферальная система (Omniston payload 0.8–1%).
- 🌐 Ton Connect 2.0 (Mini App) + мультиязычный интерфейс RU/EN.

## Стек
- Python 3.12.7+
- aiogram 3.24+, aiohttp 3.10+, tonsdk 1.0.24+
- pytonconnect (git), aiocache, loguru, pydantic-settings, sqlmodel, aiosqlite, alembic, python-dotenv

## Структура проекта
```
project_root/
├── bot/                # весь Telegram/TON код
├── config/settings.py  # Pydantic Settings
├── database/           # миграции и модели
├── locales/            # ru/en тексты
├── plugins/            # цепочки-плагины (solana, base, ...)
├── web/                # Mini App / manifest
├── requirements.txt
├── pyproject.toml
├── .env.example
└── ROADMAP.md
```

## Быстрый старт
1. Установите Python 3.12.7+ и Poetry/venv.
2. Склонируйте репозиторий и создайте окружение:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Скопируйте `.env.example` → `.env` и заполните:
   - `BOT_TOKEN` — токен @BotFather.
   - `TON_RPC_ENDPOINT`, `TON_WS_ENDPOINT` — публичные toncenter/tonhub узлы без ключей.
   - `REFERRAL_PAYLOAD` — Omniston payload 0.8–1%.
   - `DATABASE_DSN` — по умолчанию `sqlite+aiosqlite:///./database/hypersniper.db`, можно заменить на Postgres.
   - `CACHE_BACKEND` — `memory` (по умолчанию) или `redis`. Для Redis укажите `CACHE_REDIS_DSN`.
   - `JWT_SECRET` — секрет для Mini App JWT (FastAPI backend).
4. Запустите бота (пока polling):
   ```bash
   python -m bot.main
   ```
   Loader автоматически поднимет Gem Hunter и выполнит safety проверку для новых пулов.

## Middleware стек
- `I18nMiddleware` — определяет язык пользователя и прокидывает gettext.
- `ThrottlingMiddleware` — ограничивает частоту команд (по умолчанию 0.5 с).
- `DatabaseMiddleware` — выдаёт AsyncSession SQLModel на время апдейта (готово к миграциям).
- `ErrorsMiddleware` — ловит исключения, логирует и отправляет локализованное уведомление.

## Команды пользователя
- `/start` — приветствие + deep-link рефералки (формат `ref_<id>`).
- `/menu` — обзор функций и переключение языка.
- `/hot`, `/gem` — лента Gem Hunter с быстрыми покупками.
- Кнопка «👀 Подписаться» в просмотрах токена включает push-уведомления, когда он снова попадает в Alpha Scanner топ.
- `/check <jetton>` — safety отчёт по адресу JettonMinter.
- `/buy`, `/sell` — non-custodial сделки с кастомной суммой.
- `/connect`, `/wallet` — Ton Connect 2.0: ссылка на Mini App и статус кошелька (с инлайн кнопками обновления/отключения).
- `/connect` дополнительно выдаёт JWT токен, который Mini App использует в API запросах.
- `/autotp <адрес> <tp_usd> [stop_usd]` — включает auto-sell; `/autooff <ID>` отключает правило.
- `/gemfeed_on` / `/gemfeed_off` — подписка на авто-броадкаст топ-10 Gem Hunter.
- `/gemfilters score=70 lp=1 smart=2 sort=volume` — управляет фильтрами и сортировкой Alpha Scanner.
- `/referral` — статистика Omniston программы + личная deep-link ссылка.
- `/positions` — список активных правил auto-sell + текущий P&L.
- Авто-продажи уведомляют пользователя в личку сразу после срабатывания триггера.

## База данных и миграции
- Все сущности на SQLModel (`bot/models/*`): `User`, `UserSettings`, `ReferralLink`, `Position`, `GemCache`.
- Middleware `bot/middlewares/db.py` выдаёт AsyncSession; для первичного создания таблиц есть `python -m bot.scripts.init_db`.
- Alembic готов к работе: `alembic.ini` + `database/migrations/`. DSN подхватывается из `config/settings.py`.

## Mini App backend
- FastAPI (`bot/web/app.py`): `POST /api/ton-connect/link`, `POST /api/ton-connect/approve`, `GET /api/gem/top`, `POST /api/webhooks`.
- Авторизация через `Authorization: Bearer <JWT>` (токен выдаёт /connect).
- Запуск backend:
  ```bash
  uvicorn bot.web.app:app --reload --port 8000
  ```
- Frontend scaffold: `web/mini_app/` (React/Vite), манифест — `web/manifest.json`.

## Stage 7 (prod-ready)
- Логирование: `bot/logging_config.py` (JSON sink, Loguru enqueue).
- Метрики/мониторинг: планируется Prometheus exporter на FastAPI (`/metrics`).
- Тестирование: `pytest`, GitHub Actions (lint + tests).
- Деплой: docker-compose/Kubernetes (см. `docs/production.md`).

## Кеш и плагины
- `bot/utils/cache.configure_cache()` автоматически включает `aiocache.SimpleMemoryCache` или `aiocache.RedisCache` (разбор `CACHE_REDIS_DSN`, поддержка rediss://).
- Плагины цепей лежат в `plugins/`; `load_chain_plugins()` вызывает `init_plugin(context)` для каждого модуля. См. `plugins/README.md`.

## Добавление новой цепи за 10 минут
1. Создайте папку в `plugins/{chain}` с модулями `services/`, `handlers/`, `keyboards/`.
2. Реализуйте классы c теми же интерфейсами, что и TON-модуль (`DirectClient`, `SafetyChecker`, `SwapService`).
3. Опишите локали в `locales/{lang}.json`, добавьте кнопки и команды.
4. Зарегистрируйте хендлеры прямо внутри плагина — `load_chain_plugins()` импортирует все пакеты из `plugins/` при старте и активирует их код автоматически.

## Roadmap
Полный план реализации MVP и следующих этапов находится в `ROADMAP.md`. Отмечаем прогресс по мере закрытия задач, чтобы HyperSniper оставался «оружием массового поражения» в мире TON-мемкоинов.

