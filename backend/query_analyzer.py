import json
from openai import OpenAI

from backend.config import settings
from backend.prompt_templates import (
    QUERY_ANALYZER_SYSTEM_PROMPT,
    QUERY_ANALYZER_USER_PROMPT,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _safe_json_loads(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    return json.loads(text)


def analyze_question(question: str) -> dict:
    user_prompt = QUERY_ANALYZER_USER_PROMPT.format(question=question)

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": QUERY_ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    result = _safe_json_loads(content)

    # defensive defaults
    result.setdefault("route", "sql")
    result.setdefault("confidence", 0.5)
    result.setdefault("is_ambiguous", False)
    result.setdefault("clarification_question", "")
    result.setdefault("rewritten_question", question)
    result.setdefault("reasoning_summary", "")

    return result