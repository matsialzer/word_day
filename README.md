# WordDay

Telegram-бот для изучения английского: каждый день новые слова с озвучкой, мини-викторины,
интервальное повторение (Лейтнер), серии, XP, уровни, достижения и символические бонусы
усердным ученикам. Интерфейс: русский и узбекский (латиница).

Стек: Python 3.11+, aiogram 3, PostgreSQL + SQLAlchemy 2 (async) + Alembic, APScheduler,
Redis (необязательно), Docker.

## Быстрый старт (Docker)

1. Создайте бота у @BotFather, возьмите токен. Свой Telegram ID узнайте у @userinfobot.
2. `cp .env.example .env` и заполните `BOT_TOKEN` и `ADMIN_ID`.
3. `docker compose up -d --build` — поднимет Postgres, Redis и бота (миграции применяются сами).
4. Загрузите слова: `docker compose exec bot python scripts/seed_words.py`
   (образец — `data/words/*.csv`; позже слова добавляются из бота через `/admin`).
5. Озвучка: `docker compose exec bot python scripts/generate_audio.py` (бесплатный Edge TTS, нужен
   интернет), затем снова `seed_words.py`. Или положите свои mp3 в `data/audio/` (имена как в колонке
   `audio_file`) либо загружайте через `/admin`.
6. Фото к словам: зарегистрируйтесь на pixabay.com (ключ виден на pixabay.com/api/docs), впишите
   `PIXABAY_API_KEY` в `.env` и запустите `docker compose exec bot python scripts/fetch_photos.py`.
   Фото появятся в карточках урока и в вопросах «Что на картинке?».

Без Docker: нужен свой Postgres → `DATABASE_URL` в `.env`, затем
`pip install -e .`, `alembic upgrade head`, `python -m worddays.main`.

## Команды

Ученик: `/start`, `/today`, `/quiz`, `/weektest`, `/review`, `/stats`, `/streak`, `/bonus`, `/help`.
Админ: `/admin` — слов в день, словарь (добавить/импорт CSV/поиск/скрыть/озвучка), статистика,
очередь бонусов на проверку, лимиты бонусов, рассылка.

## Веб-панель администратора

Vue 3 + FastAPI: обзор и график активности, словарь (добавление, правка, скрытие, импорт CSV,
озвучка mp3), очередь бонусов, ученики (блокировка), настройки и лимиты, рассылка.

```
cd frontend && npm install && npm run build   # один раз (и после изменений интерфейса)
python -m worddays.web                         # http://127.0.0.1:8000
```

Вход по паролю `WEB_ADMIN_PASSWORD` из `.env` (без него панель не стартует). В Docker панель
поднимается сервисом `web` на `127.0.0.1:8000`; в интернет её публикуйте только за HTTPS-прокси
и тогда задайте `WEB_COOKIE_SECURE=true`. Разработка интерфейса: `npm run dev` (порт 5173,
запросы `/api` проксируются на 8000).

## Как устроено

| Слой | Где |
|---|---|
| Чистая логика (Лейтнер, XP, серии, антифрод, бонусы) | `src/worddays/core/` |
| Бизнес-сценарии | `src/worddays/services/` |
| Запросы к БД | `src/worddays/repositories/` |
| Хэндлеры, клавиатуры, тексты ru/uz | `src/worddays/bot/` |
| Веб-панель: API (FastAPI) и интерфейс (Vue) | `src/worddays/web/`, `frontend/` |
| Расписание (рассылка, напоминания, отчёты, бонусы) | `src/worddays/scheduler/` |
| Модели и миграции | `src/worddays/db/`, `migrations/` |

Планировщик каждую минуту проверяет, кому пора слать слова (по часовому поясу пользователя),
а раз в час — не пора ли сформировать бонусы за прошедшую неделю.

## Бонусы

«Усердный» за неделю: ≥5 активных дней, ≥70% верных ответов, сдан недельный тест, нет признаков
накрутки. Бот лишь формирует список (`pending`) в рамках бюджета; выплачивает админ вручную
после проверки в `/admin`. Пороги — `core/bonus.py` и `core/antifraud.py`; бюджеты и размер топа
меняются в `/admin`.

## Тесты

```
pip install -e ".[dev]"
pytest
ruff check src tests scripts
```

Тесты идут на SQLite в памяти и не требуют Postgres, токена или сети.
