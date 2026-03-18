import json
from openai import OpenAI

from backend.config import settings
from backend.prompt_templates import (
    QUERY_ANALYZER_SYSTEM_PROMPT,
    QUERY_ANALYZER_USER_PROMPT,
    FOLLOWUP_ANALYZER_SYSTEM_PROMPT,
    FOLLOWUP_ANALYZER_USER_PROMPT,
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

    result.setdefault("route", "sql")
    result.setdefault("confidence", 0.5)
    result.setdefault("is_ambiguous", False)
    result.setdefault("clarification_question", "")
    result.setdefault("rewritten_question", question)
    result.setdefault("reasoning_summary", "")

    return result


def analyze_follow_up(
    new_question: str,
    previous_question: str,
    previous_rewritten_question: str,
    previous_sql: str,
    previous_plan: dict,
) -> dict:
    user_prompt = FOLLOWUP_ANALYZER_USER_PROMPT.format(
        previous_question=previous_question or "",
        previous_rewritten_question=previous_rewritten_question or "",
        previous_sql=previous_sql or "",
        previous_plan=json.dumps(previous_plan or {}, indent=2),
        new_question=new_question,
    )

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": FOLLOWUP_ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    result = _safe_json_loads(content)

    result.setdefault("is_follow_up", False)
    result.setdefault("standalone_question", new_question)
    result.setdefault("reasoning_summary", "")

    return result