# PokerTrainer Backend

FastAPI backend для покерного GTO-тренажёра.

## Запуск

```bash
cd BackEnd
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API будет доступен на `http://localhost:8000`.

## Структура

```
BackEnd/
  app/
    main.py           — точка входа FastAPI
    core/config.py    — настройки (пути, CORS)
    db.py             — SQLAlchemy engine + сессии
    models.py         — ORM модели (spots, nodes, jobs, drill_answers)
    schemas.py        — Pydantic схемы (контракт с фронтом)
    seed.py           — загрузка seed данных из spotpack.json
    services/         — бизнес-логика
    api/              — REST-роуты
  data/
    spotpack.json     — seed данные (6 спотов + деревья)
    strategies/       — кэш стратегий (JSON)
    app.db            — SQLite БД (создаётся автоматически)
```

## Фронтенд

Для работы с бэкендом нужно задать переменные:

```
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000
```
