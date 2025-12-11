# HyperSniper Mini App (frontend)

Шаблон на React/Vite для Mini App:

1. `cd web/mini_app`
2. `npm install`
3. `npm run dev`

Переменные окружения:

- `VITE_API_BASE` — URL FastAPI backend (`https://api.hypersniper.app`)
- `VITE_TONCONNECT_APP` — manifest Mini App (если требуется).

Фронтенд должен:
- получить JWT токен от бота (/connect) и сохранить в `localStorage`;
- запрашивать `/api/ton-connect/link` и `/api/ton-connect/approve` (см. `bot/web/app.py`).




