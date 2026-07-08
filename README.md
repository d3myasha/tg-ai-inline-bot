# tg-ai-inline-bot

Telegram-бот с OpenAI-совместимым API: **чат** (личка/группа) и **inline** `@бот вопрос` (aiogram 3, long polling).

## Запуск за 3 шага

Скачай в одну папку два файла:

```bash
mkdir tg-ai-bot && cd tg-ai-bot
curl -fsSLO https://raw.githubusercontent.com/d3myasha/tg-ai-inline-bot/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/d3myasha/tg-ai-inline-bot/main/.env.example
cp .env.example .env
```

Отредактируй `.env` (минимум `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`), затем:

```bash
docker compose up -d
```

Логи: `docker compose logs -f bot`

## BotFather

Токен бота. Для inline: `/setinline` и placeholder в @BotFather.

## Переменные `.env`

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | да | Токен от @BotFather |
| `OPENAI_API_KEY` | да | Ключ API |
| `OPENAI_BASE_URL` | нет | По умолчанию `https://api.openai.com/v1` |
| `OPENAI_MODEL` | нет | По умолчанию `gpt-4o-mini` |
| `ALLOWED_TELEGRAM_USER_IDS` | нет | ID через запятую; пусто = все |

## Разработка

Клон репозитория, локальный Python или `docker build` — см. исходники в [GitHub](https://github.com/d3myasha/tg-ai-inline-bot).