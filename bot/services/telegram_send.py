from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.services.llm import truncate_for_telegram
from bot.services.telegram_format import (
    format_llm_markdown_for_telegram,
    format_llm_plain_fallback,
)


async def reply_llm_text(message: Message, raw_text: str) -> None:
    truncated = truncate_for_telegram(raw_text)
    formatted = format_llm_markdown_for_telegram(truncated)
    try:
        await message.answer(formatted)
    except TelegramBadRequest:
        await message.answer(
            format_llm_plain_fallback(truncated),
            parse_mode=ParseMode.NONE,
        )


def llm_text_for_inline(raw_text: str) -> tuple[str, ParseMode | None]:
    truncated = truncate_for_telegram(raw_text)
    formatted = format_llm_markdown_for_telegram(truncated)
    if formatted:
        return formatted, ParseMode.HTML
    return format_llm_plain_fallback(truncated), ParseMode.NONE