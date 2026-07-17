# tg-ai-inline-bot

Telegram-бот с OpenAI-совместимым API: **чат** (личка/группа через `/ai`), **inline** `@бот вопрос` (aiogram 3, long polling).

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

Токен бота. Для inline: `/setinline`, placeholder. **Обязательно** включи **inline feedback** (Collecting feedback) — без этого бот не получит `inline_message_id` и не сможет заменить «⏳ Генерирую ответ…» на ответ модели.

## Переменные `.env`

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | да | Токен от @BotFather |
| `OPENAI_API_KEY` | да | Ключ API |
| `OPENAI_BASE_URL` | нет | По умолчанию `https://api.openai.com/v1` |
| `OPENAI_MODEL` | нет | Модель по умолчанию, если пользователь не выбрал в `/model` |
| `AVAILABLE_MODELS` | нет | Фильтр поверх списка с `GET /v1/models` (пусто = все) |
| `MODELS_CACHE_TTL_SECONDS` | нет | Кэш списка моделей, по умолчанию 300 |
| `ALLOWED_TELEGRAM_USER_IDS` | нет | ID через запятую; пусто = все |

**Выбор модели:** `/model` или inline `@бот model` — список с провайдера **`GET {OPENAI_BASE_URL}/models`**. Модель **привязана к Telegram user_id** (ваш аккаунт), не к чату/группе: в личке, в группе и в inline у вас одна модель; у другого пользователя — своя. Файл: `bot-data` → `/data/user_models.json` (`{"1042345006": "gc/grok-build", ...}`).

## Разработка

Клон репозитория, локальный Python или `docker build` — см. исходники в [GitHub](https://github.com/d3myasha/tg-ai-inline-bot).