# tg-ai-inline-bot

Telegram-бот на **aiogram 3** с **inline-режимом** и OpenAI-совместимым Chat Completions API. Запуск через **Docker**.

**Режим получения апдейтов:** только **long polling** (HTTPS и домен не нужны). Webhook пока не используется.

## Возможности

- Inline: в любом чате `@your_bot ваш вопрос` → один результат с ответом модели
- `/start` в личке — краткая подсказка
- `OPENAI_BASE_URL` — любой OpenAI-compatible endpoint
- Опциональный whitelist `ALLOWED_TELEGRAM_USER_IDS`

## BotFather

1. Создай бота, получи токен.
2. `/setinline` — включи inline и задай placeholder (например: `Спроси ИИ…`).

## Конфигурация

```bash
cp .env.example .env
# отредактируй .env
```

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather |
| `OPENAI_API_KEY` | API-ключ |
| `OPENAI_BASE_URL` | База API, по умолчанию `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Имя модели |
| `ALLOWED_TELEGRAM_USER_IDS` | Через запятую; пусто = все |

## Docker (сборка локально)

```bash
docker compose up --build -d
docker compose logs -f bot
```

## Образ на GHCR

При push в `main` GitHub Actions публикует образ:

`ghcr.io/d3myasha/tg-ai-inline-bot:latest`

Запуск без локальной сборки:

```bash
cp .env.example .env
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

Первый раз может понадобиться сделать пакет **public** в GitHub → Packages → `tg-ai-inline-bot` → Package settings.

## Локально

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

## Стек

Python 3.12 · aiogram 3 · openai Python SDK · pydantic-settings · Docker

## Ограничения inline

Telegram ждёт ответ на inline-запрос быстро; длинная генерация может упираться в таймауты клиента. Для тяжёлых моделей уменьши промпт или используй быструю модель.