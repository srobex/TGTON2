# HyperSniper — запуск на Windows

Пошаговая инструкция, проверенная для Windows 10/11 PowerShell.

## 1. Предустановка
1. **Python 3.12.7+** — скачайте c python.org и во время установки отметьте “Add Python to PATH”.
2. **Git** (необязательно, но удобно для клонирования).  
3. **Redis** (опционально). Для локального теста можно использовать in-memory кеш, но продовый сценарий требует Redis.

## 2. Клонирование проекта
```powershell
git clone https://github.com/<your-org>/HyperSniper.git
cd HyperSniper
```

## 3. Создание виртуального окружения
```powershell
py -3.13 -m venv .venv
.\\.venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Настройка `.env`
Скопируйте пример и заполните значения:
```powershell
Copy-Item .env.example .env
```
Откройте `.env` в любом редакторе и заполните:

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | токен @BotFather для `@HyperSniper_bot`. |
| `TELEGRAM_ADMINS` | список Telegram ID админов (через запятую). |
| `MINI_APP_URL` | URL вашей Ton Connect Mini App (например `https://app.example.com`). |
| `WEBHOOK_DOMAIN` | домен для вебхука (если нужен webhook-режим). |
| `TON_RPC_ENDPOINT` | публичный RPC toncenter/tonhub. |
| `TON_WS_ENDPOINT` | WebSocket toncenter для JettonMinter. |
| `TON_NETWORK` | `mainnet` или `testnet`. |
| `REFERRAL_PAYLOAD` | Omniston payload 0.8–1%. |
| `REFERRAL_FEE_PERCENT` | проценты реферальной системы (0.8–1%). |
| `CACHE_BACKEND` | `memory` или `redis`. |
| `CACHE_TTL_SECONDS` | TTL кеша (например 30). |
| `CACHE_REDIS_DSN` | `redis://localhost:6379/0` (если используете Redis). |
| `DATABASE_DSN` | `sqlite+aiosqlite:///./database/hypersniper.db` либо Postgres. |
| `JWT_SECRET` | любая длинная строка (используется Mini App для JWT). |

> Совет: для тестов достаточно публичных toncenter узлов и SQLite. В проде заменить на собственные RPC + Postgres.

## 5. Инициализация базы
```powershell
python -m bot.scripts.init_db
```
Если используете Postgres, заранее создайте БД:
```powershell
psql -c "CREATE DATABASE hypersniper;"
```
и укажите DSN вида `postgresql+asyncpg://user:pass@localhost/hypersniper`.

## 6. Запуск FastAPI backend (Mini App + вебхуки)
В отдельном PowerShell-окне:
```powershell
.\\.venv\\Scripts\\activate
uvicorn bot.web.app:app --reload --port 8000
```
Endpoint’ы:
- `POST /api/ton-connect/link` — выдаёт Ton Connect ссылку (JWT в заголовке).
- `POST /api/ton-connect/approve` — сохраняет кошелёк пользователя.
- `GET /api/gem/top?limit=10` — возвращает актуальный топ токенов.
- `POST /api/webhooks` — регистрирует внешний webhook.

## 7. Запуск Telegram-бота
В другом окне PowerShell:
```powershell
.\\.venv\\Scripts\\activate
python -m bot.main
```
Бот поднимет:
- Safety checker + Ton Direct WebSocket.
- GemScanner (JettonMinter поток).
- PriceFeedService (тон-API для P&L и auto-sell).
- Auto-sell/anti-rug задачи, Gem Hunter, webhooks.

## 8. Настройка Redis (опционально)
1. Установите Redis для Windows (например, через WSL или Docker).
2. Обновите `.env`: `CACHE_BACKEND=redis`, `CACHE_REDIS_DSN=redis://localhost:6379/0`.
3. Перезапустите бот и FastAPI.

## 9. Тестирование
- **Unit tests**: `pytest` (предварительно установить `pip install pytest`).  
  ```powershell
  pytest
  ```
- **Manual QA**:  
  1. `/start` → проверить язык и реф. payload.  
  2. `/connect` → Ton Connect ссылка + JWT.  
  3. `/buy`/`/sell` (использовать тестовый Jetton).  
  4. `/autotp`, `/autooff`, `/positions`.  
  5. `/gemfeed_on` / `/gemfeed_off`.

## 10. Mini App (frontend)
```powershell
cd web\\mini_app
npm install
npm run dev
```
Настройте `.env.local` для фронта (`VITE_API_BASE=http://localhost:8000`). Mini App использует JWT, который бот отправляет в `/connect`.

## 11. Продакшн рекомендации
- См. `docs/production.md`: loguru JSON sink (`bot/logging_config.py`), план развертывания Prometheus, docker-compose/K8s.
- Разделите процессы: бот, FastAPI backend, price-feed worker.  
  Пример docker-compose сервиса:
  ```yaml
  bot:
    build: .
    command: ["python", "-m", "bot.main"]
    env_file: .env
  api:
    build: .
    command: ["uvicorn", "bot.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file: .env
  ```

Готово — после выполнения этих шагов HyperSniper работает локально на Windows и готов к боевому тестированию.




