from openai import OpenAI

from backend.config import settings
from backend.golden_queries import retrieve_similar_golden_queries
from backend.prompt_templates import (
    SQL_GENERATOR_SYSTEM_PROMPT,
    SQL_GENERATOR_USER_PROMPT,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _format_golden_examples(question: str, top_k: int = 3) -> str:
    examples = retrieve_similar_golden_queries(question, top_k=top_k)

    if not examples:
        return "No golden query examples available."

    lines = []
    for i, ex in enumerate(examples, start=1):
        lines.append(
            f"""Example {i}:
Question: {ex.get("question", "")}
SQL: {ex.get("sql", "")}
Similarity Score: {ex.get("similarity_score", 0)}
"""
        )

    return "\n".join(lines)


def generate_sql_from_plan(
    question: str,
    schema_text: str,
    plan_json: str,
    column_text: str = "",
) -> str:
    golden_examples = _format_golden_examples(question)

    user_prompt = SQL_GENERATOR_USER_PROMPT.format(
        schema_text=schema_text or "No schema provided.",
        column_text=column_text or "No column context provided.",
        question=question,
        plan_json=plan_json,
        golden_examples=golden_examples,
    )

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SQL_GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    sql = response.choices[0].message.content.strip()
    return sql.strip("`").replace("sql\n", "").strip()