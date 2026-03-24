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


# ---------------------------------------------------------
# Safe JSON parsing
# ---------------------------------------------------------
def safe_json_loads(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    return json.loads(text)


# ---------------------------------------------------------
# MAIN QUESTION ANALYZER
# ---------------------------------------------------------
def analyze_question(question: str) -> dict:

    user_prompt = QUERY_ANALYZER_USER_PROMPT.format(
        question=question
    )

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": QUERY_ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    analysis = safe_json_loads(content)

    # -------------------------------------------------
    # 🔥 LOW CONFIDENCE RULES (SCENARIO 6)
    # -------------------------------------------------
    question_lower = question.lower()

    weak_dimensions = ["region", "segment", "market", "territory"]

    if any(term in question_lower for term in weak_dimensions):

        current_conf = analysis.get("confidence", 0.7)
        analysis["confidence"] = min(current_conf, 0.5)

        # Do NOT block pipeline
        analysis["is_ambiguous"] = False

        analysis["reasoning_summary"] = (
            analysis.get("reasoning_summary", "")
            + " The question references a dimension (e.g., region) that is not explicitly "
              "available in the schema. A proxy (such as country) may be used, reducing accuracy."
        )

    return analysis


# ---------------------------------------------------------
# FOLLOW-UP ANALYZER (🔥 REQUIRED FOR YOUR APP)
# ---------------------------------------------------------
def analyze_follow_up(
    new_question: str,
    previous_question: str,
    previous_rewritten_question: str,
    previous_sql: str,
    previous_plan: dict,
) -> dict:

    user_prompt = FOLLOWUP_ANALYZER_USER_PROMPT.format(
        previous_question=previous_question,
        previous_rewritten_question=previous_rewritten_question,
        previous_sql=previous_sql,
        previous_plan=json.dumps(previous_plan, indent=2),
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

    return safe_json_loads(content)