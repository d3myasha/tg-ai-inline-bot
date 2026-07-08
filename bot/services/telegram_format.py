import html as html_lib
import re

import bleach
import markdown

_ALLOWED_TAGS = [
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "code",
    "pre",
    "a",
    "tg-spoiler",
]
_ALLOWED_ATTRS = {"a": ["href"]}


def _tables_to_pre(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        block = re.sub(r"</tr>\s*<tr>", "\n", block, flags=re.IGNORECASE)
        block = re.sub(r"</t[hd]>\s*<t[hd]>", " | ", block, flags=re.IGNORECASE)
        plain = re.sub(r"<[^>]+>", "", block)
        plain = html_lib.unescape(plain.strip())
        return f"<pre>{html_lib.escape(plain)}</pre>" if plain else ""

    return re.sub(r"<table[\s\S]*?</table>", repl, html, flags=re.IGNORECASE)


def format_llm_markdown_for_telegram(text: str) -> str:
    """Markdown from the model → Telegram HTML (parse_mode=HTML)."""
    if not text.strip():
        return ""

    try:
        raw_html = markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
            output_format="html5",
        )
        for level in range(6, 0, -1):
            raw_html = re.sub(
                rf"<h{level}[^>]*>(.*?)</h{level}>",
                r"<b>\1</b>\n\n",
                raw_html,
                flags=re.DOTALL | re.IGNORECASE,
            )
        raw_html = _tables_to_pre(raw_html)
        raw_html = re.sub(
            r"<li[^>]*>(.*?)</li>",
            r"• \1\n",
            raw_html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        raw_html = re.sub(r"</?[uo]l[^>]*>", "\n", raw_html, flags=re.IGNORECASE)
        raw_html = re.sub(
            r"<p[^>]*>(.*?)</p>",
            r"\1\n\n",
            raw_html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        raw_html = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)

        cleaned = bleach.clean(
            raw_html,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            strip=True,
        )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned
    except Exception:
        return f"<pre>{html_lib.escape(text)}</pre>"


def format_llm_plain_fallback(text: str) -> str:
    return html_lib.escape(text)


def plain_preview(text: str, max_len: int = 256) -> str:
    plain = re.sub(r"[#*_`>\[\]()]", "", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= max_len:
        return plain
    return plain[: max_len - 3] + "..."