# --- сборка Vue-интерфейса админ-панели ---
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# --- приложение ---
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Сначала зависимости - слой кэшируется, пока pyproject не менялся
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY data ./data
COPY --from=frontend /frontend/dist ./frontend/dist

# Применяем миграции и запускаем бота
CMD ["sh", "-c", "alembic upgrade head && python -m worddays.main"]
