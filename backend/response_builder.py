import json
from typing import Any
from openai import OpenAI

from backend.config import settings
from backend.prompt_templates import (
    FOLLOWUP_SUGGESTION_SYSTEM_PROMPT,
    FOLLOWUP_SUGGESTION_USER_PROMPT,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def detect_chart_spec(plan: dict[str, Any], columns: list[str], rows: list[list[Any]]) -> dict[str, Any] | None:
    if not rows or len(columns) < 2:
        return None

    lowered_cols = [c.lower() for c in columns]
    intent = (plan or {}).get("intent", "")

    # Time series
    if any(token in lowered_cols[0] for token in ["date", "month", "year", "quarter", "week"]) and len(columns) >= 2:
        if isinstance(rows[0][1], (int, float)):
            return {
                "chart_type": "line",
                "x": columns[0],
                "y": columns[1],
                "title": "Trend over time",
            }

    # Aggregation / category comparisons
    if intent in {"aggregation", "comparison", "distribution", "trend"}:
        if isinstance(rows[0][1], (int, float)):
            return {
                "chart_type": "bar",
                "x": columns[0],
                "y": columns[1],
                "title": "Comparison by category",
            }

    return None


def build_insight_text(
    question: str,
    route: str,
    plan: dict[str, Any],
    columns: list[str],
    rows: list[list[Any]],
) -> str:
    if not rows:
        return "No results were returned for this query."

    row_count = len(rows)
    preview = rows[0]

    intent = plan.get("intent", "unknown")
    grouping = plan.get("grouping", [])
    aggregations = plan.get("aggregations", [])

    parts = [
        f"Returned {row_count} row(s).",
        f"Intent: {intent}.",
    ]

    if grouping:
        parts.append(f"Grouped by: {', '.join(grouping)}.")

    if aggregations:
        parts.append(f"Metrics: {', '.join(aggregations)}.")

    if columns and preview:
        try:
            first_row_pairs = ", ".join(
                f"{col}={val}" for col, val in zip(columns[:4], preview[:4])
            )
            parts.append(f"Top result preview: {first_row_pairs}.")
        except Exception:
            pass

    if route == "hybrid":
        parts.append("This response combines SQL results with document context.")

    return " ".join(parts)


def _safe_json_loads(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    return json.loads(text)


def generate_follow_up_suggestions(
    question: str,
    route: str,
    plan: dict[str, Any],
    columns: list[str],
) -> list[str]:
    try:
        user_prompt = FOLLOWUP_SUGGESTION_USER_PROMPT.format(
            question=question,
            route=route,
            plan_json=json.dumps(plan or {}, indent=2),
            columns=", ".join(columns or []),
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": FOLLOWUP_SUGGESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        result = _safe_json_loads(content)
        follow_ups = result.get("follow_ups", [])

        if isinstance(follow_ups, list):
            return [str(x) for x in follow_ups[:3]]

    except Exception:
        pass

    return [
        "Can you break this down by month?",
        "Can you show the top 5 instead?",
        "Can you include more detail columns?",
    ]


def build_structured_response(
    *,
    route: str,
    original_question: str,
    rewritten_question: str,
    confidence: float,
    analysis: dict[str, Any],
    plan: dict[str, Any],
    sql: str,
    columns: list[str],
    rows: list[list[Any]],
    request_id: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    chart = detect_chart_spec(plan, columns, rows)
    insights = build_insight_text(
        question=original_question,
        route=route,
        plan=plan,
        columns=columns,
        rows=rows,
    )
    follow_ups = generate_follow_up_suggestions(
        question=rewritten_question,
        route=route,
        plan=plan,
        columns=columns,
    )

    return {
        "success": True,
        "route": route,
        "question": original_question,
        "rewritten_question": rewritten_question,
        "confidence": confidence,
        "analysis": analysis,
        "plan": plan,
        "sql": sql,
        "result": {
            "type": "table",
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        },
        "chart": chart,
        "insights": insights,
        "follow_ups": follow_ups,
        "sources": sources or [],
        "request_id": request_id,
    }