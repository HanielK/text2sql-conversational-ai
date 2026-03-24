from openai import OpenAI

from backend.config import settings
from backend.golden_queries import retrieve_similar_golden_queries
from backend.prompt_templates import (
    SQL_GENERATOR_SYSTEM_PROMPT,
    SQL_GENERATOR_USER_PROMPT,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ---------------------------------------------------------
# 🔥 FORMAT GOLDEN EXAMPLES (UPGRADED)
# ---------------------------------------------------------

def _format_golden_examples(question: str, top_k: int = 3) -> str:
    examples = retrieve_similar_golden_queries(question, top_k=top_k)

    # 🔥 Filter weak matches (CRITICAL)
    examples = [e for e in examples if e.get("similarity_score", 0) > 0.6]

    if not examples:
        return "No highly relevant validated query patterns available."

    lines = ["### 🔥 VALIDATED QUERY PATTERNS (PRIORITY SIGNAL)\n"]

    for i, ex in enumerate(examples, start=1):
        lines.append(
            f"""Example {i} (Similarity: {ex.get("similarity_score", 0)})

User Question:
{ex.get("question", "")}

Correct SQL:
{ex.get("sql", "")}
"""
        )

    lines.append(
        "\nIMPORTANT INSTRUCTIONS:\n"
        "- These are proven, validated queries\n"
        "- Reuse JOIN logic, filters, and aggregations when relevant\n"
        "- Prefer adapting these patterns over creating new ones\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------
# 🔥 SQL GENERATION (UPGRADED)
# ---------------------------------------------------------

def generate_sql_from_plan(
    question: str,
    schema_text: str,
    plan_json: str,
    column_text: str = "",
) -> str:

    # 🔥 Retrieve golden examples
    golden_examples = _format_golden_examples(question)

    # 🔍 (OPTIONAL DEBUG — HIGHLY RECOMMENDED)
    if settings.DEBUG:
        print("\n" + "=" * 60)
        print("🧠 GOLDEN EXAMPLES USED:")
        print(golden_examples)
        print("=" * 60)

    # -----------------------------------------------------
    # Build prompt
    # -----------------------------------------------------
    user_prompt = SQL_GENERATOR_USER_PROMPT.format(
        golden_examples=golden_examples,  # 🔥 moved to top priority
        schema_text=schema_text or "No schema provided.",
        column_text=column_text or "No column context provided.",
        plan_json=plan_json,
        question=question,
    )

    # -----------------------------------------------------
    # Call LLM
    # -----------------------------------------------------
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SQL_GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    sql = response.choices[0].message.content.strip()

    # -----------------------------------------------------
    # 🔥 CLEAN SQL OUTPUT (ROBUST)
    # -----------------------------------------------------
    sql = (
        sql.replace("```sql", "")
        .replace("```", "")
        .replace("sql\n", "")
        .strip()
    )

    return sql