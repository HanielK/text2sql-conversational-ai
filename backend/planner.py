import json
from openai import OpenAI

from backend.config import settings
from backend.prompt_templates import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def safe_json_loads(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    return json.loads(text)


def build_query_plan(
    question: str,
    schema_text: str,
    column_text: str = "",
) -> dict:
    user_prompt = PLANNER_USER_PROMPT.format(
        schema_text=schema_text or "No schema provided.",
        column_text=column_text or "No column context provided.",
        question=question,
    )

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    plan = safe_json_loads(content)

    if "limit" not in plan or not isinstance(plan["limit"], int):
        plan["limit"] = settings.SQL_ROW_LIMIT

    return plan