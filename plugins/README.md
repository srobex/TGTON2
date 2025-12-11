# Плагины HyperSniper

## Как создать плагин цепи
1. Создайте папку `plugins/<chain>` и реализуйте `__init__.py` с функцией `init_plugin(context)`.
2. В `context` доступны:
   - `dp`, `bot`, `settings`
   - `services`: `safety_checker`, `gem_scanner`, `swap_service`, `ton_connect`
3. Внутри `init_plugin` подключите свои хендлеры (`dp.include_router(...)`), сервисы и планировщики.

Примеры: `plugins/solana/`, `plugins/base/`.




