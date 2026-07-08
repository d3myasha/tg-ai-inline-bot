import html as html_lib


def build_llm_reply_markdown(user_query: str, answer: str) -> str:
    question = user_query.strip()
    body = answer.strip()
    if not question:
        return body
    return f"**Вопрос:** {question}\n\n{body}"


def build_llm_reply_html(user_query: str, answer: str) -> str:
    question = user_query.strip()
    body = answer.strip()
    if not question:
        return body
    q_esc = html_lib.escape(question)
    return f"<b>Вопрос:</b> {q_esc}\n\n{body}"