def build_llm_reply_markdown(user_query: str, answer: str) -> str:
    question = user_query.strip()
    body = answer.strip()
    if not question:
        return body
    return f"**Вопрос:** {question}\n\n{body}"
