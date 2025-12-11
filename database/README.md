# База данных HyperSniper

## Инициализация
1. Убедись, что `.env` содержит `DATABASE_DSN`.
2. Прогони первичное создание таблиц (до первых миграций):
   ```bash
   python -m bot.scripts.init_db
   ```
   либо используй `SQLModel.metadata.create_all` в `bot/middlewares/db.py`.

## Alembic
- Конфиг: `alembic.ini`
- Скрипты: `database/migrations/`

### Команды
```bash
# новая миграция
alembic revision -m "create users table"

# применить
alembic upgrade head

# откат
alembic downgrade -1
```

`env.py` автоматически подтягивает DSN из `config.settings`. Для async-драйверов (`aiosqlite`) строка преобразуется в sync-вариант.




