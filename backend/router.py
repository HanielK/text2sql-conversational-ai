import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)


def route_question(question: str) -> str:
    prompt = f"""
Classify the user question into exactly one of these routes:

- sql = structured database question best answered with SQL
- doc = unstructured document question best answered from documents
- hybrid = requires both SQL data and document context

Examples:
- "show all orders" -> sql
- "summarize the project scope document" -> doc
- "compare the delivery plan with current order metrics" -> hybrid

Question:
{question}

Return only one word:
sql
doc
hybrid
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    route = response.choices[0].message.content.strip().lower()

    if route not in {"sql", "doc", "hybrid"}:
        return "sql"

    return route