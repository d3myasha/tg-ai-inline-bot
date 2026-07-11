from openai import AsyncOpenAI

from bot.config import Settings


def create_openai_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url.rstrip("/"),
    )


async def complete_chat(
    client: AsyncOpenAI,
    settings: Settings,
    user_text: str,
    *,
    model: str | None = None,
) -> str:
    response = await client.chat.completions.create(
        model=model or settings.openai_model,
        messages=[
            {"role": "system", "content": settings.assistant_system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
        timeout=120,
    )
    choice = response.choices[0].message.content
    if not choice:
        return "Модель вернула пустой ответ."
    return choice.strip()


def truncate_for_telegram(text: str, max_len: int = 4096) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"